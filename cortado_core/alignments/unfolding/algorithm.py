from typing import Set

from pm4py import PetriNet, Marking
from pm4py.objects.petri_net.utils.align_utils import (
    SKIP,
    STD_MODEL_LOG_MOVE_COST,
    construct_standard_cost_function,
)

from cortado_core.alignments.unfolding.unfold import UnfoldingAlgorithm
from cortado_core.alignments.unfolding.unfold_improved import UnfoldingAlgorithmImproved
from cortado_core.alignments.unfolding.visualization import draw_unfolded_alignment, save_prefix_as_png


def unfold_sync_net(
    sync_net: PetriNet,
    initial_marking: Marking,
    final_marking: Marking,
    sync_trans: Set[PetriNet.Transition],
    cost_function: dict = None,
    improved: bool = True,
    bid: str = None,
    trace_net=None,
    trace_net_fm=None,
    with_heuristic=False,
):
    if cost_function is None:
        cost_function = construct_standard_cost_function(sync_net, SKIP)

    # improved = False

    if not improved:
        algo = UnfoldingAlgorithm(
            sync_net, sync_trans, initial_marking, final_marking, cost_function, trace_net, trace_net_fm
        )
    else:
        algo = UnfoldingAlgorithmImproved(
            with_heuristic, sync_net, sync_trans, initial_marking, final_marking, cost_function, trace_net,
            trace_net_fm
        )

    alignment = algo.search()

    # print(alignment.num_cutoffs)
    # print(alignment.alignment_costs)
    # print(f'(queued, visited): ({alignment.queued_events}, {alignment.visited_events})')

    # draw_unfolded_alignment(alignment, f'unfolded_alignment_{bid}')
    # # #
    # # # # draw prefix
    # save_prefix_as_png(alignment.generated_prefix, f'prefix{bid}')

    results = {
        "alignments": [],
        "costs": alignment.alignment_costs,
        "deviations": alignment.alignment_costs // STD_MODEL_LOG_MOVE_COST,
        "deviation_deps": [],
        "time_taken": alignment.total_duration,
        "(queued, visited)": (alignment.queued_events, alignment.visited_events),
        "time_taken_potext": alignment.time_taken_potext,
    }

    # for log_graph, model_graph, sync_moves in process_unfolded_alignment(alignment):
    #
    #     # TODO:- add a switch later for this feature
    #     remove_silent_nodes_reconnect_edges(log_graph)
    #     remove_silent_nodes_reconnect_edges(model_graph)
    #
    #     # count the number of dependencies in each graph
    #     log_deps = set(log_graph.edges())
    #     model_deps = set(model_graph.edges())
    #
    #     deps_in_log_but_not_model = log_deps - model_deps
    #     deps_in_model_but_not_log = model_deps - log_deps
    #
    #     for dep in deps_in_log_but_not_model:
    #         results["deviation_deps"].append(Dependency(str(dep[0]), str(dep[1]), True,
    #                                                     dep[0].is_synchronous and dep[1].is_synchronous))
    #
    #     for dep in deps_in_model_but_not_log:
    #         results["deviation_deps"].append(Dependency(str(dep[0]), str(dep[1]), False,
    #                                                     dep[0].is_synchronous and dep[1].is_synchronous))
    #
    #     # to also consider number of deviations wrt dependencies
    #     # + order matters, hence counting the symmetric difference
    #     results["deviations"] += len(model_deps ^ log_deps)
    #
    #     v_log_object = generate_variant_object(log_graph)
    #     v_model_object = generate_variant_object(model_graph)
    #
    #     results["alignments"].append(
    #         (
    #             v_log_object,
    #             v_model_object,
    #         )
    #     )

    return results
