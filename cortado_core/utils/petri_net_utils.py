import math
from collections import defaultdict

import networkx
import networkx as nx
from pm4py.objects.log.obj import Trace
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.objects.petri_net.utils import petri_utils

from cortado_core.utils.constants import PartialOrderMode


def _generate_networkx_graph(petri_net: PetriNet):
    graph = networkx.DiGraph()
    for place in petri_net.places:
        graph.add_node(place)
    for transition in petri_net.transitions:
        graph.add_node(transition)
        for a in transition.out_arcs:
            target_place = a.target
            graph.add_edge(transition, target_place)
        for a in transition.in_arcs:
            source_place = a.source
            graph.add_edge(source_place, transition)
    return graph


def get_all_paths_between_transitions(
    petri_net: PetriNet,
    transition1: PetriNet.Transition,
    transition2: PetriNet.Transition,
):
    g = _generate_networkx_graph(petri_net)
    return networkx.all_simple_paths(g, transition1, transition2)


def get_all_distances(petri_net: PetriNet):
    return networkx.shortest_path_length(_generate_networkx_graph(petri_net))


def get_distances_from_transitions_to_places(petri_net: PetriNet):
    """
    Returns the distances from all transitions to all reachable places.
    The distance denotes the number of arcs in the petri_net.
    """
    distances = get_all_distances(petri_net)
    res = {}
    for source, distances in distances:
        if type(source) is PetriNet.Transition:
            res[source] = defaultdict(
                lambda: math.inf,
                {
                    target.name: distances[target]
                    for target in distances
                    if type(target) is PetriNet.Place
                },
            )
    return res


def get_transitions_by_label(petri_net: PetriNet, label: str):
    res = set()
    for t in petri_net.transitions:
        if t.label == label:
            res.add(t)
    return res


def get_partial_trace_net_from_trace(
    trace: Trace,
    mode: PartialOrderMode = PartialOrderMode.NONE,
    add_artificial_start_and_end: bool = True,
    key_start_timestamp: str = "start_timestamp",
    key_end_timestamp: str = "time:timestamp",
    activity_key: str = "concept:name",
) -> tuple[PetriNet, Marking, Marking]:
    """Converts a given trace into a Petri net.

    Parameters:
        trace: Trace to be converted into a Petri net.
        mode: Possible values: CLOSURE, REDUCTION, NONE (default)
        add_artificial_start_and_end: Add an artificial start and end activity (if necessary)
        key_start_timestamp: Key of the start timestamp.
        key_end_timestamp: Key of the end timestamp.
        activity_key: Key of the activity.

    Returns:
        Petri net and its initial and final marking.
    """
    events = {f"t_{e[activity_key]}_{i}": e[activity_key] for i, e in enumerate(trace)}

    edges, start_events, end_events = get_partial_order_from_trace(
        trace, mode, key_start_timestamp, key_end_timestamp
    )

    if add_artificial_start_and_end:
        # add artificial start if more than one start event
        if len(start_events) > 1:
            events["S"] = None
            edges = edges + [("S", s) for s in start_events]
            start_events = ["S"]

        # add artificial start if more than one start event
        if len(end_events) > 1:
            events["E"] = None
            edges = edges + [(e, "E") for e in end_events]
            end_events = ["E"]

    # create new petri net
    net = PetriNet()
    initial_marking = Marking()
    final_marking = Marking()

    # add events as transitions
    transitions = {}
    for event_id, event in events.items():
        transition = PetriNet.Transition(event_id, event)
        transitions[event_id] = transition
        net.transitions.add(transition)

        # add initial marking if event is start event
        if event_id in start_events:
            p_i = PetriNet.Place(f"p_i{len(initial_marking)}")
            net.places.add(p_i)
            petri_utils.add_arc_from_to(p_i, transition, net)
            initial_marking[p_i] = 1

        # add final marking if event is end event
        if event_id in end_events:
            p_o = PetriNet.Place(f"p_o{len(final_marking)}")
            net.places.add(p_o)
            petri_utils.add_arc_from_to(transition, p_o, net)
            final_marking[p_o] = 1

    # add dependencies as places
    for edge_idx, (source, target) in enumerate(edges):
        place = PetriNet.Place(f"p_{edge_idx}")
        net.places.add(place)
        petri_utils.add_arc_from_to(transitions[source], place, net)
        petri_utils.add_arc_from_to(place, transitions[target], net)

    return net, initial_marking, final_marking


def get_partial_order_from_trace(
    trace: Trace,
    mode: PartialOrderMode = PartialOrderMode.NONE,
    key_start_timestamp: str = "start_timestamp",
    key_end_timestamp: str = "time:timestamp",
    activity_key: str = "concept:name",
) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    events = {e: (e[key_start_timestamp], e[key_end_timestamp]) for e in trace}
    inserted_events = {}

    partial_order = nx.DiGraph()
    for event_idx, (event, (start, end)) in enumerate(events.items()):
        event_id = f"t_{event[activity_key]}_{event_idx}"
        partial_order.add_node(event_id)
        inserted_events[event_id] = (start, end)

        # check for dependencies to already inserted nodes
        for event_id2, (start2, end2) in inserted_events.items():
            if start > end2:
                partial_order.add_edge(event_id, event_id2)

    if mode == PartialOrderMode.REDUCTION:
        partial_order = nx.transitive_reduction(partial_order)
    elif mode == PartialOrderMode.CLOSURE:
        partial_order = nx.transitive_closure(partial_order)

    # find start and end activities
    start_events = [node for node, deg in partial_order.out_degree() if deg == 0]
    end_events = [node for node, deg in partial_order.in_degree() if deg == 0]

    dependencies = [(u, v) for v, u in partial_order.edges]

    return dependencies, start_events, end_events
