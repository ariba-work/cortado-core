from typing import Set

from cachetools import cached
from cachetools.keys import hashkey
from pm4py import PetriNet

from cortado_core.alignments.unfolding.obj.configuration import Configuration

class BranchingProcess(object):
    class OccurrenceNet(PetriNet):
        def __init__(
            self, name=None, conditions=None, events=None, arcs=None, properties=None
        ):
            super().__init__(
                name,
                places=conditions,
                transitions=events,
                arcs=arcs,
                properties=properties,
            )
            self._conditions = (
                list() if conditions is None else conditions
            )  # list to easily fetch them
            # by index for generating combinations
            self._events = list() if events is None else events
            self._global_visited = (
                0  # to 'reset' after searches in O(1) time. See pg. 145 verifik
            )
            # TODO: enforce - 1. acyclic nature, 2. no event is in self-conflict, 3. each node has a finite preset

        def __str__(self):
            return (
                f"Occurrence Net: conditions={self._conditions}, events={self._events}"
            )

        @property
        def conditions(self):
            return self._conditions

        @conditions.setter
        def conditions(self, value):
            self._conditions = value

        @property
        def events(self):
            return self._events

        @events.setter
        def events(self, value):
            self._events = value

        @property
        def global_visited(self):
            return self._global_visited

        @global_visited.setter
        def global_visited(self, value):
            self._global_visited = value

        class Condition(PetriNet.Place):
            def __init__(self, mapped_place=None, in_arcs=None, **kw):
                if in_arcs and len(in_arcs) > 1:
                    raise Exception(
                        "Occurrence Nets cannot have more than one incoming arc to conditions"
                    )
                PetriNet.Place.__init__(
                    self, **kw
                )  # name will be exploited to store id (idx x) of conditions
                self._mapped_place: PetriNet.Place = mapped_place
                self._visited = None
                self._coset = set()

            def __str__(self):
                return f"Condition {self.name}: pi(c)={self.mapped_place}"

            def __repr__(self):
                return f"Condition(mapped_place={self.mapped_place}, name=c{self.name})"

            def __eq__(self, other):
                return self.name == other.name

            def __hash__(self):
                return hash(self.name)

            @property
            def mapped_place(self):
                return self._mapped_place

            @mapped_place.setter
            def mapped_place(self, value):
                self._mapped_place = value

            @property
            def visited(self):
                return self._visited

            @visited.setter
            def visited(self, value):
                self._visited = value

            @property
            def coset(self):
                return self._coset

            @coset.setter
            def coset(self, value):
                self._coset = value

        class Event(PetriNet.Transition):
            def __init__(
                self,
                mapped_transition=None,
                local_configuration=None,
                cost=None,
                **kw,
            ):
                PetriNet.Transition.__init__(
                    self, **kw
                )  # name will be exploited to store id (idx y) of events
                self._mapped_transition = mapped_transition
                self._local_configuration = (
                    Configuration({self})
                    if local_configuration is None
                    else local_configuration
                )
                self._visited = None
                self._cost = 0 if cost is None else cost
                self._mark = None

            def __str__(self):
                return (
                    f"Event {self.name}: pi(e)={self.mapped_transition}, [e]={self.local_configuration},"
                    f" total cost:{self.local_configuration.total_cost + self.local_configuration.h}"
                )

            def __repr__(self):
                return (
                    f"Event(mapped_transition={self.mapped_transition}, "
                    f"name=e{self.name}, "
                    f"local_configuration={self.local_configuration})"
                )

            # def __lt__(self, other):
            #     return self.name < other.name

            @property
            def mapped_transition(self):
                return self._mapped_transition

            @mapped_transition.setter
            def mapped_transition(self, value):
                self._mapped_transition = value

            @property
            @cached(cache={}, key=lambda self: id(self))
            def local_configuration(self):
                configuration_events = {self}
                pred_events = {
                    pre_in_arc.source
                    for pre in self.preset
                    for pre_in_arc in pre.in_arcs
                }

                for pred_event in pred_events:
                    for e in pred_event.local_configuration.events:
                        configuration_events.add(e)

                return Configuration(configuration_events)

            @local_configuration.setter
            def local_configuration(self, value):
                self._local_configuration = value

            @property
            def visited(self):
                return self._visited

            @visited.setter
            def visited(self, value):
                self._visited = value

            @property
            def cost(self):
                return self._cost

            @cost.setter
            def cost(self, value):
                self._cost = value

            @property
            def mark(self):
                return self._mark

            @mark.setter
            def mark(self, value):
                self._mark = value

            def __lt__(self, other):
                return self.local_configuration < other.local_configuration

    def __init__(
        self,
        net: PetriNet = None,
        occurrence_net: OccurrenceNet = None,
        cost_function=None,
    ):
        self._net = net
        self._occurrence_net = occurrence_net
        self._cost_function = cost_function

    @property
    def net(self):
        return self._net

    @net.setter
    def net(self, value):
        self._net = value

    @property
    def occurrence_net(self):
        return self._occurrence_net

    @occurrence_net.setter
    def occurrence_net(self, value):
        self._occurrence_net = value

    @property
    def cost_function(self):
        return self._cost_function

    @cost_function.setter
    def cost_function(self, value):
        self._cost_function = value

