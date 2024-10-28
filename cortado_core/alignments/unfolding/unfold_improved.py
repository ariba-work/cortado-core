import functools
import heapq
import itertools
import time
from collections import deque
from typing import FrozenSet, Dict, Set, Tuple, List

from cvxopt import matrix
from pm4py import PetriNet, Marking
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to

from cortado_core.alignments.unfolding.obj.branching_process import BranchingProcess
from cortado_core.alignments.unfolding.unfold import UnfoldingAlgorithm
from cortado_core.alignments.unfolding.utils import (
    UnfoldingAlignment,
    UnfoldingAlignmentResult,
)
from pm4py.objects.petri_net.utils.incidence_matrix import construct as inc_mat_construct
from cortado_core.alignments.unfolding.heuristic_utils import compute_exact_heuristic, vectorize_initial_final_cost, \
    vectorize_matrices


class UnfoldingAlgorithmImproved(UnfoldingAlgorithm):
    def __init__(self, unfold_with_heuristic: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unfold_with_heuristic = unfold_with_heuristic

        self.incidence_matrix = inc_mat_construct(self.net)
        self.ini_vec, self.fin_vec, self.cost_vec = \
            vectorize_initial_final_cost(self.incidence_matrix, self.initial_marking, Marking({self.tp: 1}),
                                         self.cost_function)
        self.a_matrix, self.g_matrix, self.h_cvx = vectorize_matrices(self.incidence_matrix, self.net)
        self.cost_vec = matrix([x * 1.0 for x in self.cost_vec])

    def _init_search(self):
        """
        Initializes the search by creating the initial branching process, queue
        and additionally calculates the possible extensions for the initial marking
        as they are added to the prefix

        """

        self.prefix = BranchingProcess.OccurrenceNet()
        self.process = BranchingProcess(self.net, self.prefix, self.cost_function)
        self.queue = []
        self.cutoffs: Set[BranchingProcess.OccurrenceNet.Event] = set()
        self.induced_markings: Dict[
            FrozenSet[PetriNet.Place], BranchingProcess.OccurrenceNet.Event
        ] = {}
        self.alignment = UnfoldingAlignment()

        self.comatrix = {}

        im = set()
        # add conditions possible in initial marking
        for p_init in list(self.initial_marking.keys()):
            self.add_condition(p_init)
            im.add(p_init)
        self.induced_markings[frozenset(im)] = BranchingProcess.OccurrenceNet.Event(name="dummy")

        for c in self.prefix.conditions:
            self.calculate_possible_extensions(c)


    def add_event(
        self,
        mapped_transition: PetriNet.Transition,
        cset: List[BranchingProcess.OccurrenceNet.Condition],
    ):
        """
        adds an event to the queue and to the prefix, extending from the given set of conditions
        Args:
            mapped_transition ():
            cset ():

        Returns:

        """

        self.y += 1
        e = BranchingProcess.OccurrenceNet.Event(
            mapped_transition, name=self.y, cost=self.cost_function[mapped_transition]
        )

        self.extend_cset_to_event(cset, e)

        m = self.compute_mark(e)
        e.mark = m.union(e.mapped_transition.postset)

        # directed unfolding cost function
        if self.unfold_with_heuristic:
            h, x = compute_exact_heuristic(self.net, self.a_matrix, self.h_cvx, self.g_matrix, self.cost_vec,
                                           self.incidence_matrix, Marking({p: 1 for p in e.mark}), self.fin_vec)
            e.local_configuration.h = h

        self.prefix.events.append(e)

        heapq.heappush(self.queue, e)
        self.queued += 1

    def add_condition(self, mapped_place: PetriNet.Place):
        """
        Adds a condition to the prefix and updates the inverse map of the mapped place

        """

        self.x += 1
        c = BranchingProcess.OccurrenceNet.Condition(
            mapped_place=mapped_place, name=self.x
        )
        self.prefix.conditions.append(c)

        # update inverse map
        if (
            "inverse_map" not in mapped_place.properties
        ):  # exploiting the `properties` dict to store `inverse map`
            mapped_place.properties["inverse_map"] = deque()
        mapped_place.properties["inverse_map"].append(c)

        return c

    def event_already_exists(
        self,
        mapped_transition: PetriNet.Transition,
        preset: Set[BranchingProcess.OccurrenceNet.Condition],
    ):
        """
        checks if the event is not already added

        """
        cset_postset = set(
            functools.reduce(
                lambda x, y: x.intersection(y), map(lambda x: x.postset, preset)
            )
        )
        return any(c.mapped_transition == mapped_transition for c in cset_postset)

    def calculate_possible_extensions(
        self, c: BranchingProcess.OccurrenceNet.Condition
    ):
        """
        Optimization to not consider all possible combinations - adapted from Algorithm 8.8
        `Theorie und Praxis der Netzentfaltungen als Grundlage für die Verifikation nebenläufiger Systeme` by Roemer

        """

        start_time = time.time()

        if isinstance(c, list):
            return

        for oarc in c.mapped_place.out_arcs:
            t = oarc.target

            if len(t.in_arcs) == 1:
                self.add_event(t, [c])

            elif len(t.in_arcs) == 2:
                s = [arc.source for arc in t.in_arcs if arc.source != c.mapped_place][
                    0
                ]  # will always be one

                if "inverse_map" in s.properties:
                    for c_prime in s.properties["inverse_map"]:
                        if self.is_co_set((c_prime, c)):
                            if (self.event_already_exists(t, {c_prime, c})
                                or len(c_prime.preset.intersection(self.cutoffs)) != 0):
                                continue

                            self.add_event(t, [c_prime, c])

            else:
                # set of places excluding the mapped place
                s_n = [arc.source for arc in t.in_arcs if arc.source != c.mapped_place]

                # Efficient Cartesian product generation and filtering
                for tup in itertools.product(
                    *[
                        sn_i.properties["inverse_map"]
                        if "inverse_map" in sn_i.properties else []
                        for sn_i in s_n
                    ]
                ):
                    # Ensure that each element in the tuple is not in conflict with `c`
                    if not all(self.is_co_set((c, c_prime)) for c_prime in tup):
                        continue

                    # Ensure that no pair of elements in the tuple is in conflict with each other
                    if not all(self.is_co_set(cond_pair) for cond_pair in itertools.combinations(tup, 2)):
                        continue

                    # Check if the event already exists before adding
                    if self.event_already_exists(t, set(tup).union({c})):
                        continue

                    # Add the event if it passes all checks
                    self.add_event(t, list(tup) + [c])

        self.time_tracker.add_time(time.time() - start_time)

    def is_co_set(
        self,
        cset: Tuple[
            BranchingProcess.OccurrenceNet.Condition,
            BranchingProcess.OccurrenceNet.Condition,
        ],
    ):
        """
        deep-search to look for conflicts or causality - check first if co-set is already in comatrix
        if not, update the result in comatrix
        """

        if cset in self.comatrix:
            return self.comatrix[cset]

        if cset[::-1] in self.comatrix:
            return self.comatrix[cset[::-1]]

        res = super().is_co_set(list(cset))

        self.comatrix[cset] = res

        return res

    def search(self):
        """
        Main search function. It initializes the search, and then iteratively selects events, according to
        a cost-based order so that the prefix is extended only towards the shortest path direction

        Returns:
            UnfoldingAlignmentResult: result of the search, containing the alignment, its cost, number of cutoffs and
            the time taken to find the alignment
        """

        self._init_search()

        while self.queue:

            e: BranchingProcess.OccurrenceNet.Event = heapq.heappop(self.queue)
            self.visited += 1
            # if cost of path already exceeded, no need to extend, cutoff
            if (
                self.alignment.lowest_cost is not None
                and e.local_configuration.total_cost + e.local_configuration.h
                > self.alignment.lowest_cost
            ):
                # print('cost of path already exceeded, adding to cutoff')
                self.cutoffs.add(e)
                continue

            # if `e` is final event, we found one of the shortest paths, add to alignment
            if e.mapped_transition.name == "tr":
                self.alignment.final_events.add(e)
                self.alignment.lowest_cost = e.local_configuration.total_cost
                if self.stop_at_first:
                    break

            if len(e.local_configuration.events.intersection(self.cutoffs)) == 0:
                condts_to_add = []

                # add `e`'s postset conditions to prefix, extending from `e` one by one
                for s in e.mapped_transition.postset:
                    c = self.add_condition(s)
                    condts_to_add.append(c)
                    add_arc_from_to(e, c, self.prefix)

                if self.is_cutoff(e):
                    self.cutoffs.add(e)

                else:
                    # calculate possible extensions for each NEW condition added
                    for c in condts_to_add:
                        self.calculate_possible_extensions(c)

        elapsed_time = time.time() - self.start_time

        return UnfoldingAlignmentResult(
            self.alignment, len(self.cutoffs), self.prefix, elapsed_time, self.visited, self.queued, time_taken_potext=self.time_tracker.get_total_time()
        )
