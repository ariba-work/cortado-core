import functools
import heapq
import time
from collections import deque
from typing import Set, List, Dict, FrozenSet

from cachetools import cached
from cachetools.keys import hashkey
from pm4py import PetriNet, Marking
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to

from cortado_core.alignments.unfolding.obj.branching_process import BranchingProcess
from cortado_core.alignments.unfolding.obj.time_tracker import TimeTracker
from cortado_core.alignments.unfolding.utils import (
    add_final_state,
    UnfoldingAlignment,
    UnfoldingAlignmentResult,
)
from cortado_core.utils.constants import SKIP


class UnfoldingAlgorithm:
    def __init__(
        self,
        sync_net: PetriNet,
        initial_marking: Marking,
        final_marking: Marking,
        cost_function: dict[PetriNet.Transition, int],
        time_tracker: TimeTracker =None,
    ):
        self.start_time = time.time()
        self.cost_function = cost_function
        self.initial_marking = initial_marking
        self.final_marking = final_marking

        self.net = sync_net

        _, tp = add_final_state(self.net, self.final_marking, self.cost_function)
        self.tp = tp

        self.x = -1  # our conditions and events numbering starts from 0
        self.y = -1  # unlike the MacMillan algo where it starts from 1
        self.process = None
        self.prefix = None
        self.queue = None
        self.cutoffs = None
        self.induced_markings = None

        self.alignment = None
        self.stop_at_first = True
        self.unfold_with_heuristic = None

        self.visited = 0
        self.queued = 0

        self.time_tracker = time_tracker if time_tracker else TimeTracker()

    def _init_search(self):

        self.prefix = BranchingProcess.OccurrenceNet()
        self.process = BranchingProcess(self.net, self.prefix, self.cost_function)
        self.queue = []
        self.cutoffs: Set[BranchingProcess.OccurrenceNet.Event] = set()
        self.induced_markings: Dict[
            FrozenSet[PetriNet.Place], BranchingProcess.OccurrenceNet.Event
        ] = {}
        self.alignment = UnfoldingAlignment()

        im = set()
        # add conditions possible in initial marking
        for p_init in list(self.initial_marking.keys()):
            self.add_condition(p_init)
            im.add(p_init)
        self.induced_markings[frozenset(im)] = BranchingProcess.OccurrenceNet.Event(name="dummy")

        # add possible extensions for each initial condition
        curr_conditions = self.prefix.conditions.copy()
        for c in curr_conditions:
            self.calculate_possible_extensions([c])

    def compute_h(
        self,
        mark: frozenset[PetriNet.Place],
    ):
        if len(mark) == 0:
            return 0
        else:
            return self.d_sum(mark)

    def add_condition(self, mapped_place: PetriNet.Place):
        """
        adds a condition to the list of prefix conditions with name as `x+1`
        :param mapped_place:
        :type mapped_place:
        :return:
        :rtype:
        """
        self.x += 1
        c = BranchingProcess.OccurrenceNet.Condition(
            mapped_place=mapped_place, name=self.x
        )
        self.prefix.conditions.append(c)

        return c

    def add_final_state(self):
        # print(f'adding final state from {self.final_marking.keys()} to tr')

        final_places: Set[PetriNet.Place] = set(self.final_marking.keys())

        tr = PetriNet.Transition(preset=final_places, name="tr", label="tr")
        pr = PetriNet.Place(preset={tr}, name="pr", label="pr")

        add_arc_from_to(tr, pr, self.net)

        for fp in final_places:
            add_arc_from_to(fp, tr, self.net)

        self.net.transitions.add(tr)
        self.net.places.add(pr)

        self.cost_function.update({tr: 0})

    def mark_visited(self, condition: BranchingProcess.OccurrenceNet.Condition):
        condition.visited = self.prefix.global_visited

    def inc_visit_counter(self):
        self.prefix.global_visited += 1

    def is_co_set(self, cset: List[BranchingProcess.OccurrenceNet.Condition]):
        """
        deep-search to look for conflicts or causality - the most naive way

        ### Main Steps in `is_co_set` Method

        1. **Trivial Co-set Check**:
           - If the set of conditions (`cset`) is empty or has only one condition, it is trivially a co-set. Return `True`.

        2. **Initialize Stack and Visit Counter**:
           - Initialize a stack to keep track of conditions to be processed.
           - Increment the global visit counter.

        3. **Mark Initial Conditions and Their Predecessors**:
           - For each condition in `cset`, mark it as visited.
           - If the condition has a predecessor, mark the predecessor and add it to the stack.

        4. **Depth-First Search for Conflicts**:
           - While the stack is not empty, pop a condition from the stack.
           - For each predecessor of the popped condition, check if it has already been visited in the current search.
             - If a visited condition is found, return `False` (indicating a conflict).
             - Otherwise, mark the predecessor and add its predecessor to the stack if it exists.

        5. **Return Result**:
           - If no conflicts are found during the search, return `True`.

        :param cset:
        :type cset:
        :return:
        :rtype:
        """

        # if the set is empty or has only one condition, it is trivially a co-set
        if len(cset) < 2:
            return True

        stack = deque()
        self.inc_visit_counter()

        for c in cset:
            self.mark_visited(c)

            c_pre = list(c.preset)[0] if len(c.preset) > 0 else None
            if c_pre is not None and c_pre.visited != self.prefix.global_visited:
                self.mark_visited(c_pre)
                stack.append(c_pre)

        while stack:
            e = stack.pop()

            for c in e.preset:
                if c.visited == self.prefix.global_visited:
                    return False

                self.mark_visited(c)

                c_pre = list(c.preset)[0] if len(c.preset) > 0 else None

                if c_pre is not None and c_pre.visited != self.prefix.global_visited:
                    self.mark_visited(c_pre)
                    stack.append(c_pre)

        return True

    def early_stop(self, cset: List[BranchingProcess.OccurrenceNet.Condition]):
        """
        early stop according to MacMillan's improvements, either:
            1. if `cset` is not `co-set` (conditions are not in 'co-relation' or are in 'self-conflict'), or
            2. if there exists no transition whose preset contains `place(cset)`
                (no transition is enabled by the conditions)
        :param cset: set of conditions to compare
        :type cset: List[Condition]
        :return: True if no such transition is found or the conditions are not in co-relation, False otherwise
        :rtype: boolean
        """

        trans_found = False
        mapped_places = set(map(lambda x: x.mapped_place, cset))

        for t in self.net.transitions:
            if mapped_places.issubset(t.preset):
                trans_found = True
                break

        if not trans_found or not self.is_co_set(cset):
            return True

        return False

    def extend_cset_to_event(
        self,
        cset: List[BranchingProcess.OccurrenceNet.Condition],
        e: BranchingProcess.OccurrenceNet.Event,
    ):
        for c in cset:
            add_arc_from_to(c, e, self.prefix)

    def calculate_possible_extensions(
        self, cset: List[BranchingProcess.OccurrenceNet.Condition]
    ):
        """
        calculates possible extensions for a given set of conditions. combinatorial problem of selecting sets of
        conditions such that their mapped places enable a transition in the net. Since the combinatorial problem can
        be time expensive, improvements to stop early and to avoid redundant extensions are implemented.

        ### Main Steps

        1. **Early Stop Check**:
           - Call the `early_stop` method with the given set of conditions (`cset`).
           - If `early_stop` returns `True`, exit the method.

        2. **Initialize Mapped Places and Postset**:
           - Create a set of mapped places from the conditions in `cset`.
           - Create a set of postset events by intersecting the postsets of all conditions in `cset`.

        3. **Add Events for Transitions**:
           - Iterate over all transitions in the Petri net.
           - For each transition, check if its preset is exactly equal to the set of mapped places.
           - If the preset matches, check if an event for this transition already exists in the postset.
           - If no such event exists, add a new event to the queue and the prefix.

        4. **Depth-First Search for Extensions**:
           - Iterate over all conditions in the prefix that are older than the conditions in `cset`.
           - For each condition, create a new set by adding this condition to `cset`.
           - Recursively call `calculate_possible_extensions` with the new set of conditions.

        Args:
            cset (): set of conditions to extend

        Returns:
            void
        """

        start_time = time.time()

        if self.early_stop(cset):
            return

        # Initialize Mapped Places and Postset
        mapped_places = set(map(lambda x: x.mapped_place, cset))
        cset_postset = set(
            functools.reduce(
                lambda x, y: x.intersection(y), map(lambda x: x.postset, cset)
            )
        )

        # for all the transitions in the net, if the preset of the transition is exactly equal to the `places(cset)`,
        # then add an event to the queue and to the prefix, extending from the `cset`
        # but only if there is no such event already in the prefix
        for t in self.net.transitions:
            if t.preset == mapped_places:
                for ev in cset_postset:
                    if ev.mapped_transition == t:
                        break

                else:
                    self.add_event(t, cset)

        # for all the conditions in the net older than every condition in the `cset`
        # calculate extensions for its union with the `cset` => depth first search of all possible combinations
        for i in range(cset[-1].name + 1, self.x + 1):
            tmp = cset.copy()
            tmp.append(self.prefix.conditions[i])
            self.calculate_possible_extensions(tmp)

        self.time_tracker.add_time(time.time() - start_time)

    def compute_mark(
        self, event: BranchingProcess.OccurrenceNet.Event
    ) -> frozenset[PetriNet.Place]:

        conf = event.local_configuration.events
        conf_pre = conf_post = set()

        for e in conf:
            conf_pre = conf_pre.union(e.preset)
        # Mark(e) computed as per MacMillan's paper: `Mark(e) = pi((Min(prefix) U [e]*]) - *[e])`
        mark = (
            set(self.prefix.conditions[: len(self.initial_marking.keys())]).union(
                conf_post
            )
        ).difference(conf_pre)
        mark = frozenset(map(lambda x: x.mapped_place, mark))

        return mark

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

        self.prefix.events.append(e)

        heapq.heappush(self.queue, e)
        self.queued += 1

    def is_cutoff(self, event: BranchingProcess.OccurrenceNet.Event):
        """
        checks if the given event is a cutoff, i.e. if its induced marking is already induced by some other event in the
        prefix. If so, the event is a cutoff and the prefix need not be extended on this path. If not, the marking is
        added to the induced markings dictionary for future reference.

        Args:p
            event (): event to check

        Returns:
            boolean: True if the event is a cutoff, False otherwise

        """
        if event.mapped_transition.name == "tr":
            return False

        mark = self.compute_mark(event)

        if mark in self.induced_markings:
            return True
        else:
            self.induced_markings[mark] = event
            return False

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
                and e.local_configuration.total_cost > self.alignment.lowest_cost
            ):
                self.cutoffs.add(e)
                continue

            # if `e` is final event, we found one of the shortest paths, add to alignment
            if e.mapped_transition.name == "tr":
                # print(f"final event found!")
                self.alignment.final_events.add(e)
                self.alignment.lowest_cost = e.local_configuration.total_cost
                if self.stop_at_first:
                    break

            if len(e.local_configuration.events.intersection(self.cutoffs)) == 0:
                # add `e`'s postset conditions to prefix, extending from `e` one by one
                for s in e.mapped_transition.postset:
                    c = self.add_condition(s)
                    add_arc_from_to(e, c, self.prefix)

                # identify possible extensions for ALL the conditions in updated conditions
                curr_conditions = self.prefix.conditions.copy()
                for c in curr_conditions:
                    self.calculate_possible_extensions([c])

                if self.is_cutoff(e):
                    self.cutoffs.add(e)

        elapsed_time = time.time() - self.start_time

        return UnfoldingAlignmentResult(
            self.alignment, len(self.cutoffs), self.prefix, elapsed_time, self.visited, self.queued, time_taken_potext=self.time_tracker.get_total_time()
        )
