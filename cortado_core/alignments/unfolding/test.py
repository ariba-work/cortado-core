import random
import string
from os.path import join

import click as click
import pm4py
from pm4py import PetriNet, Marking, convert_to_petri_net
from pm4py import save_vis_petri_net
from pm4py.objects.conversion.process_tree.variants.to_petri_net import clean_duplicate_transitions
from pm4py.objects.log.importer.xes.importer import apply as xes_import
from pm4py.objects.log.util.interval_lifecycle import to_interval
from pm4py.objects.petri_net.importer import importer as petri_importer
from pm4py.objects.petri_net.utils.align_utils import SKIP
from pm4py.objects.petri_net.utils.petri_utils import add_arc_from_to, remove_transition
from pm4py.objects.petri_net.utils.synchronous_product import construct
from pm4py.objects.petri_net.utils.synchronous_product import construct as construct_synchronous_product
from pm4py.util.xes_constants import DEFAULT_START_TIMESTAMP_KEY

from cortado_core.alignments.unfolding.algorithm import unfold_sync_net
from cortado_core.utils.constants import PartialOrderMode
from cortado_core.utils.petri_net_utils import get_partial_trace_net_from_trace


def main():
    # create places for model net
    p0 = PetriNet.Place("p0", label="p0")
    p1 = PetriNet.Place("p1", label="p1")
    p2 = PetriNet.Place("p2", label="p2")
    # p3 = PetriNet.Place("p3", label="p3")

    # create places for log net
    p00 = PetriNet.Place("p00", label="p(.,b)")
    p01 = PetriNet.Place("p01", label="p(b,c)")
    p02 = PetriNet.Place("p02", label="p(c,d)")
    p03 = PetriNet.Place("p03", label="p(c,e)")
    p04 = PetriNet.Place("p04", label="p(d,.)")
    p05 = PetriNet.Place("p05", label="p(e,.)")

    # create transitions for model
    t0 = PetriNet.Transition(name="t0", label="b")
    t1 = PetriNet.Transition(name="t1", label="c")
    t2 = PetriNet.Transition(name="t2")  # skip transition
    t3 = PetriNet.Transition(name="t3", label="f")
    # t4 = PetriNet.Transition(name="t4", label="a")

    # create transitions for log
    tb = PetriNet.Transition(name="tb", label="b")
    tc = PetriNet.Transition(name="tc", label="c")
    td = PetriNet.Transition(name="td", label="d")
    te = PetriNet.Transition(name="te", label="e")

    # Create Petri nets (example)
    log_net = PetriNet("log_net", places=[p00, p01, p02, p03, p04, p05], transitions=[tb, tc, td, te])
    model_net = PetriNet("model_net", places=[p0, p1, p2], transitions=[t0, t1, t2, t3])

    # create arcs for model
    add_arc_from_to(p0, t0, model_net)
    add_arc_from_to(p0, t1, model_net)
    add_arc_from_to(t0, p1, model_net)
    add_arc_from_to(t1, p1, model_net)
    add_arc_from_to(p1, t2, model_net)
    add_arc_from_to(t2, p0, model_net)
    add_arc_from_to(p1, t3, model_net)
    add_arc_from_to(t3, p2, model_net)
    # add_arc_from_to(p3, t4, model_net)
    # add_arc_from_to(t4, p0, model_net)

    # create arcs for log
    add_arc_from_to(p00, tb, log_net)
    add_arc_from_to(tb, p01, log_net)
    add_arc_from_to(p01, tc, log_net)
    add_arc_from_to(tc, p02, log_net)
    add_arc_from_to(tc, p03, log_net)
    add_arc_from_to(p02, td, log_net)
    add_arc_from_to(p03, te, log_net)
    add_arc_from_to(td, p04, log_net)
    add_arc_from_to(te, p05, log_net)

    # Define initial and final markings (example)
    im_log = Marking()
    im_log[p00] = 1

    fm_log = Marking()
    fm_log[p05] = 1
    fm_log[p04] = 1

    im_model = Marking()
    im_model[p0] = 1

    fm_model = Marking()
    fm_model[p2] = 1

    # create synchronous product net
    sync_net, sync_im, sync_fm = construct(log_net, im_log, fm_log, model_net, im_model, fm_model, SKIP)

    # Visualize the synchronous net
    save_vis_petri_net(sync_net, sync_im, sync_fm, 'spn.png')

    # Call unfold_sync_net with the Petri net and markings
    results = unfold_sync_net(sync_net, sync_im, sync_fm)

    # Print the results
    print("Alignment Results:")
    print(results)


@click.command()
@click.option('--path', '-p', help='Path to the data directory.')
@click.option('--log', '-l', help='Name of the event log.')
@click.option('--model', '-m', help='Name of the process model.')
def compute_unfolding_based_alignments(path: str, log: str, model: str):

    # pt1 = pm4py.read_ptml(join(f'.', path, model))
    # model_net, model_im, model_fm = convert_to_petri_net(pt1)

    # model_net = clean_duplicate_transitions(model_net)


    # save_vis_petri_net(model_net, model_im, model_fm, f'data/viz/sync_product/model.png')
    model_net, model_im, model_fm = petri_importer.apply(join(f'.', path, model))
    event_log = xes_import(join(f'.', path, log))

    if (
        DEFAULT_START_TIMESTAMP_KEY not in event_log[0][0]
    ):
        event_log = to_interval(event_log)[:]

    total_duration = 0

    for trace_idx, trace in enumerate(event_log, 1):



        # build trace net
        net, im, fm = get_partial_trace_net_from_trace(trace, PartialOrderMode.REDUCTION, False)

        # save_vis_petri_net(net, im, fm, f'data/viz/sync_product/log.png')
        # trace_order_relations = get_partial_order_relations_from_trace(trace)

        # build SPN
        sync_prod, sync_im, sync_fm, sync_trans = construct_synchronous_product(net, im, fm, model_net, model_im, model_fm, SKIP)
        # save_vis_petri_net(sync_prod, sync_im, sync_fm, f'data/viz/sync_product/${trace_idx}.png')

        # compute alignments
        # print(f'\nunfolding sync prod net for trace:{trace_idx}')

        # print(f'{trace_idx}::')
        result = unfold_sync_net(sync_prod, sync_im, sync_fm, sync_trans, bid=str(trace_idx), trace_net=net, trace_net_fm=fm)
        # print(f'time taken: {result["time_taken"]}')

        total_duration += result["time_taken"]

        # for log_graph, model_graph, sync_moves in process_unfolded_alignment(alignment):
        #     print(list(log_graph.nodes()))
        #     print(list(model_graph.nodes()))
        #
        # print(f'#nodes explored: {len(alignment.generated_prefix.events)}')
        # print(f'time taken: {round(result["time_taken"] * 1000, 3)} ms')

        # # process alignments
        # draw_finite_prefix(alignment.generated_prefix, f'data/viz/alignments/unfolding/${trace_idx}',
        #                    label=f'Alignment costs: {alignment.alignment_costs} '
        #                          f'\nfor the event: e{alignment.final_event_name}'
        #                          f'\nnumber of nodes in prefix: {len(alignment.generated_prefix.conditions)}'
        #                          f'\ntime to compute: {round(alignment.total_duration * 1000, 3)} ms')

        # draw_unfolded_alignment(alignment, f'data/viz/alignments/unfolding/${trace_idx}_alignment')

    print(f'total time taken: {round(total_duration * 1000, 3)} ms')

@click.command()
@click.option('--tree1', '-t1', help='Path to tree 1')
@click.option('--tree2', '-t2', help='Path to tree 2')
def compute_unfolding_based_alignments_from_trees(tree1: str, tree2: str):

    pt1 = pm4py.read_ptml(tree1)
    pn1, im1, fm1 = convert_to_petri_net(pt1)
    pt2 = pm4py.read_ptml(tree2)
    pn2, im2, fm2 = convert_to_petri_net(pt2)

    for net in (pn1, pn2):
        for t in net.transitions:
            if t.label is None:
                t.label = ''.join(random.choices(string.ascii_letters, k=4))

    # save_vis_petri_net(pn1, im1, fm1, f'data/viz/sync_product/pn1.png')
    # save_vis_petri_net(pn2, im2, fm2, f'data/viz/sync_product/pn2.png')

    sync_prod, sync_im, sync_fm, sync_trans = construct_synchronous_product(pn1, im1, fm1, pn2, im2, fm2, SKIP)
    save_vis_petri_net(sync_prod, sync_im, sync_fm, f'data/viz/sync_product/trees_1_1+1_2.png')

    # Generate the reachability graph
    # ts = reachability_graph.construct_reachability_graph(sync_prod, sync_im)
    # print(f'Number of states in the reachability graph: {len(ts.states)}')
    # Visualize the reachability graph using PM4Py's visualization module
    # gviz = ts_visualizer.apply(ts)

    # Save the visualization as an image or view it directly
    # ts_visualizer.view(gviz)

    result = unfold_sync_net(sync_prod, sync_im, sync_fm, sync_trans)
    print(f'time taken: {round(result["time_taken"] * 1000, 3)} ms')
    print(f'alignment costs: {result["costs"]}')



@click.group()
def cli():
    pass


cli.add_command(compute_unfolding_based_alignments, "unfolding-based-alignments")
cli.add_command(compute_unfolding_based_alignments_from_trees, "unfolding-based-alignments-trees")

if __name__ == '__main__':
    cli()
