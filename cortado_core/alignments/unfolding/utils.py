from collections import deque
from typing import Set

import networkx as nx
import numpy as np
from pm4py import Marking, PetriNet
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to

from cortado_core.alignments.unfolding.obj.branching_process import BranchingProcess
from cortado_core.alignments.unfolding.obj.po_node import PONode
from cortado_core.utils.constants import DependencyTypes, SKIP, SILENT_TRANSITION
from cortado_core.utils.split_graph import split_graph


class UnfoldingAlignment:
    def __init__(
        self,
        final_events: Set[BranchingProcess.OccurrenceNet.Event] = None,
        lowest_cost: int = None,
    ):
        self.final_events = set() if final_events is None else final_events
        self.lowest_cost = lowest_cost


class UnfoldingAlignmentResult:
    def __init__(
        self,
        alignment: UnfoldingAlignment,
        num_cutoffs,
        generated_prefix: BranchingProcess.OccurrenceNet = None,
        total_duration: float = 0,
    ):
        self.final_events = alignment.final_events
        self.alignment_costs = alignment.lowest_cost
        self.num_cutoffs = num_cutoffs
        self.total_duration = total_duration
        self.generated_prefix = generated_prefix
        self.final_event_name = list(map(lambda x: x.name, alignment.final_events))


def add_final_state(
    net: PetriNet, fm: Marking, cost_function: dict[PetriNet.Transition, int]
):
    """
    Adds a final transition `tr` extending from the final marking of the given net and a final place `pr` following `tr`.
    cost of the final transition is set to 0.
    Args:
        net (): petri net to be extended
        fm (): final marking of the given net
        cost_function (): cost function to be updated

    Returns:
        void
    """

    # print(f'adding final state from {fm.keys()} to tr')

    final_places: Set[PetriNet.Place] = set(fm.keys())

    tr = PetriNet.Transition(preset=final_places, name="tr", label="tr")
    tp = PetriNet.Place(preset={tr}, name="pr", label="pr")

    for fp in final_places:
        add_arc_from_to(fp, tr, net)

    add_arc_from_to(tr, tp, net)

    net.places.add(tp)
    net.transitions.add(tr)

    cost_function.update({tr: 0})

    return tr, tp


def _get_type(move: tuple[str]):
    if move[0] != SKIP and move[1] == SKIP:
        return DependencyTypes.LOG.value

    if move[0] != SKIP and move[1] != SKIP:
        return DependencyTypes.SYNCHRONOUS.value

    return DependencyTypes.MODEL.value


def _get_move_label(move):
    if not move[0] or not move[1]:  # silent transition
        return SILENT_TRANSITION  # tau

    if move[0] != SKIP:  # log move
        return move[0]

    return move[1]  # model move


def process_unfolded_alignment(alignment: UnfoldingAlignmentResult):
    unfolded_alignments = []

    for event in alignment.final_events:
        log_graph = nx.DiGraph()
        model_graph = nx.DiGraph()
        log_graph, model_graph, sync_moves = add_node_and_edges_bfs(
            log_graph, model_graph, event, 0
        )
        unfolded_alignments.append((log_graph, model_graph, sync_moves))

    return unfolded_alignments


def add_node_and_edges_bfs(log_graph, model_graph, start_event, sync_moves):
    # Initialize the queue with the starting event
    # since `t` was artificially added for the shortest path computation, we need to NOT include it
    queue = deque([list(condition.preset)[0] for condition in start_event.preset])

    while queue:
        event = queue.popleft()

        move_type = _get_type(event.mapped_transition.name)
        move_label = _get_move_label(event.mapped_transition.label)
        node = PONode(move_label, event.name)

        if move_type == DependencyTypes.MODEL.value:
            model_graph.add_node(node)
        elif move_type == DependencyTypes.LOG.value:
            log_graph.add_node(node)
        else:
            sync_moves += 1
            node.is_synchronous = True
            model_graph.add_node(node)
            log_graph.add_node(node)

        for condition in event.preset:
            c_pre = list(condition.preset)[0] if len(condition.preset) > 0 else None

            if c_pre:
                source = PONode(_get_move_label(c_pre.mapped_transition.label), c_pre.name,
                                _get_type(c_pre.mapped_transition.name) == DependencyTypes.SYNCHRONOUS.value)
                target = node
                dep_type = _get_type(condition.mapped_place.name)

                if dep_type == DependencyTypes.MODEL.value:
                    model_graph.add_edge(source, target)
                elif dep_type == DependencyTypes.LOG.value:
                    log_graph.add_edge(source, target)
                else:
                    model_graph.add_edge(source, target)
                    log_graph.add_edge(source, target)

                # Enqueue the predecessor event
                queue.append(c_pre)

    return log_graph, model_graph, sync_moves


def generate_follows_parallel_graphs(graph):
    g_follows = nx.transitive_closure(graph, reflexive=None)
    adjacency_matrix = nx.adjacency_matrix(
        g_follows, nodelist=list(nx.topological_sort(g_follows))
    )
    iden = np.tri(adjacency_matrix.shape[0], adjacency_matrix.shape[1], -1).transpose()
    inv_mat = iden - adjacency_matrix
    inv_mat = inv_mat.clip(min=0)
    g_parallel = nx.from_numpy_array(inv_mat, create_using=nx.DiGraph)
    mapping = dict(enumerate(nx.topological_sort(g_follows)))
    g_parallel = nx.relabel_nodes(g_parallel, mapping)

    return g_follows, g_parallel


def generate_variant_object(graph: nx.DiGraph):
    # component based cuts on the partial order
    g_follows, g_parallel = generate_follows_parallel_graphs(graph)
    variant = split_graph(g_follows, g_parallel)
    variant.assign_dfs_ids()
    return variant.serialize()


def remove_silent_nodes_reconnect_edges(graph):
    nodes_to_remove = [node for node in graph.nodes() if node.label == SILENT_TRANSITION]

    for node in nodes_to_remove:
        predecessors = list(graph.predecessors(node))
        successors = list(graph.successors(node))

        for pred in predecessors:
            for succ in successors:
                graph.add_edge(pred, succ)

        graph.remove_node(node)
