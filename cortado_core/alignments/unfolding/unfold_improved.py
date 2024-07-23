import functools
import heapq
import itertools
import time
from collections import deque
from typing import FrozenSet, Dict, Set, Tuple

from pm4py import PetriNet
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to

from cortado_core.alignments.unfolding.obj.branching_process import BranchingProcess
from cortado_core.alignments.unfolding.unfold import UnfoldingAlgorithm
from cortado_core.alignments.unfolding.utils import (
    UnfoldingAlignment,
    UnfoldingAlignmentResult,
)


class UnfoldingAlgorithmImproved(UnfoldingAlgorithm):
    def __init__(self, unfold_with_heuristic: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unfold_with_heuristic = unfold_with_heuristic

        # self.incidence_matrix = inc_mat_construct(self.net)
        # self.ini_vec, self.fin_vec, self.cost_vec = \
        #     vectorize_initial_final_cost(self.incidence_matrix, self.initial_marking, self.final_marking,
        #                                  self.cost_function)
        # self.a_matrix, self.g_matrix, self.h_cvx = vectorize_matrices(self.incidence_matrix, self.net)
        # self.cost_vec = matrix([x * 1.0 for x in self.cost_vec])

    def _init_search(self):
        """
        Initializes the search by creating the initial branching process, queue
        and additionally calculates the possible extensions for the initial marking
        as they are added to the prefix

        """

        # print('\ninitializing search...')

        self.prefix = BranchingProcess.OccurrenceNet()
        self.process = BranchingProcess(self.net, self.prefix, self.cost_function)
        self.queue = []
        self.cutoffs: Set[BranchingProcess.OccurrenceNet.Event] = set()
        self.induced_markings: Dict[
            FrozenSet[PetriNet.Place], BranchingProcess.OccurrenceNet.Event
        ] = {}
        self.alignment = UnfoldingAlignment()

        self.comatrix = {}

        # add conditions possible in initial marking
        for p_init in list(self.initial_marking.keys()):
            self.add_condition(p_init)

        for c in self.prefix.conditions:
            self.calculate_possible_extensions(c)

        # print('initialization done')

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

        # print(f'added condition {c} to prefix')

        return c

    def event_already_exists(
        self,
        mapped_transition: PetriNet.Transition,
        preset: Set[BranchingProcess.OccurrenceNet.Condition],
    ):
        """
        Adds an event to the queue and to the prefix, extending from the given set of conditions
        and additionally checks if the event is not already added

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
        # print(f'calculating possible extensions (improved) for condition {c}')

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
                            if self.event_already_exists(t, {c_prime, c}):
                                continue

                            self.add_event(t, [c_prime, c])

            else:
                # set of places excluding the mapped place
                s_n = [arc.source for arc in t.in_arcs if arc.source != c.mapped_place]

                # cartesian product of inverse maps of all places in s_n
                k = {
                    tup
                    for tup in itertools.product(
                        *[
                            sn_i.properties["inverse_map"]
                            if "inverse_map" in sn_i.properties
                            else []
                            for sn_i in s_n
                        ]
                    )
                }

                # filter k to only include tuples where each of its element is not in conflict with c
                k = {
                    tup
                    for tup in k
                    for idx, c_prime in enumerate(tup)
                    if self.is_co_set((c, c_prime))
                }

                # filter k to only include tuples where each pair of its elements is not in conflict with each other
                for tup in k:
                    if all(
                        self.is_co_set(cond_pair)
                        for cond_pair in itertools.combinations(tup, 2)
                    ):
                        if self.event_already_exists(t, set(tup).union({c})):
                            continue

                        self.add_event(t, list(tup) + [c])

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

        # print('checking co-set...')

        if tuple(cset) in self.comatrix:
            # print('co-set found in comatrix')
            return self.comatrix[tuple(cset)]

        res = super().is_co_set(list(cset))

        self.comatrix[tuple(cset)] = res

        return res

    #
    # def compute_h(self, m: frozenset[UPetriNet.UPlace]):
    #     marking = {p: 1 for p in m}
    #     return compute_exact_heuristic(self.net, self.a_matrix, self.h_cvx, self.g_matrix, self.cost_vec,
    #                                    self.incidence_matrix, marking, self.fin_vec)

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
            # print(f'queue size: {len(self.queue)}')
            e: BranchingProcess.OccurrenceNet.Event = heapq.heappop(self.queue)
            # print(f'popped event {e} from queue')

            # if cost of path already exceeded, no need to extend, cutoff
            if (
                self.alignment.lowest_cost is not None
                and e.local_configuration.total_cost + e.h_sum
                > self.alignment.lowest_cost
            ):
                # print('cost of path already exceeded, adding to cutoff')
                self.cutoffs.add(e)
                continue

            # if `e` is final event, we found one of the shortest paths, add to alignment
            if e.mapped_transition.name == "tr":
                print(f"final event found!")
                self.alignment.final_events.add(e)
                print(f"transition costs: {e.local_configuration.total_cost}")
                print(f"heuristics costs: {e.h_sum}")
                # print(self.prefix.events)
                self.alignment.lowest_cost = e.local_configuration.total_cost + e.h_sum
                if self.stop_at_first:
                    break

            # print(f'${e}: {e.preset}')
            # print(e.local_configuration.events)
            # print(self.cutoffs)
            if len(e.local_configuration.events.intersection(self.cutoffs)) == 0:
                condts_to_add = []

                # add `e` and its conditions for its postset to prefix
                for s in e.mapped_transition.postset:
                    c = self.add_condition(s)
                    condts_to_add.append(c)
                    add_arc_from_to(e, c, self.prefix)

                for c in condts_to_add:
                    self.calculate_possible_extensions(c)

                if self.is_cutoff(e):
                    self.cutoffs.add(e)

        # print(f'\nsearch done.')
        elapsed_time = time.time() - self.start_time
        # print(f'time taken: {elapsed_time} seconds')
        # print(f'cutoffs ({len(self.cutoffs)}): {self.cutoffs}')
        # print(f'prefix: total events={len(self.prefix.events)}, total conditions={len(self.prefix.conditions)}')
        # if self.alignment.lowest_cost is not None:
        #     print(f'alignment: {self.alignment.final_events}, total cost: {self.alignment.lowest_cost}')

        return UnfoldingAlignmentResult(
            self.alignment, len(self.cutoffs), self.prefix, elapsed_time
        )
