import csv
import os
import random
import string
from os.path import join

import click as click
import pm4py
from pm4py import PetriNet, Marking, convert_to_petri_net, write_pnml
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

import signal
from pm4py.objects.petri_net.exporter import exporter as pn_exporter

header = ['variant', 'trace_idx', 'trace_length', 'time_taken', 'time_taken_potext', 'queued_events', 'visited_events', 'alignment_costs']


# Define a timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Trace processing timed out")

# Set the timeout duration (in seconds)
timeout_duration = 100  # Adjust as needed

# Register the timeout handler
signal.signal(signal.SIGALRM, timeout_handler)


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
    # save_vis_petri_net(sync_net, sync_im, sync_fm, 'spn.png')

    # Call unfold_sync_net with the Petri net and markings
    results = unfold_sync_net(sync_net, sync_im, sync_fm)

    # Print the results
    print("Alignment Results:")
    print(results)


def process_trace(trace_idx, trace, model_net, model_im, model_fm, with_heuristic):
    try:
        # Set the alarm
        signal.alarm(timeout_duration)

        # build trace net
        net, im, fm = get_partial_trace_net_from_trace(trace, PartialOrderMode.REDUCTION, False)

        # build SPN
        sync_prod, sync_im, sync_fm = construct_synchronous_product(net, im, fm, model_net, model_im, model_fm, SKIP)

        result = unfold_sync_net(sync_prod, sync_im, sync_fm, bid=str(trace_idx), with_heuristic=with_heuristic)

        output = [
            with_heuristic,
            trace_idx,
            len(trace),
            result["time_taken"],
            result['time_taken_potext'],
            result["(queued, visited)"][0],
            result["(queued, visited)"][1],
            result["costs"],
        ]

        return output

    except TimeoutError:
        print(f"Trace {trace_idx} processing timed out")
        return [
            with_heuristic,
            trace_idx,
            len(trace),
            "timeout",
            "timeout",
            "timeout",
            "timeout",
            "timeout",
        ]

    finally:
        # Disable the alarm
        signal.alarm(0)


@click.command()
@click.option('--path', '-p', help='Path to the data directory.')
@click.option('--log', '-l', help='Name of the event log.')
@click.option('--model', '-m', help='Name of the process model.')
@click.option('--heuristics', '-h', help='0/1 to run with heuristics.')
def compute_unfolding_based_alignments(path: str, log: str, model: str, heuristics: int):

    with_heuristic = bool(int(heuristics))

    print(f'running experiment for with heuristics={with_heuristic}..')

    model_net, model_im, model_fm = petri_importer.apply(join(f'.', path, model))

    event_log = xes_import(join(f'.', path, log))

    if (
        DEFAULT_START_TIMESTAMP_KEY not in event_log[0][0]
    ):
        event_log = to_interval(event_log)[8:9]

    print(f'total number of traces: {len(event_log)}')

    with open(f'experiments/results/{model}.csv', mode='a', newline='') as output:

        writer = csv.writer(output)

        for trace_idx, trace in enumerate(event_log, 1):
            result = process_trace(trace_idx, trace, model_net, model_im, model_fm, with_heuristic)
            writer.writerow(result)

        print(f'completed for model={model}, closing file')

    output.close()


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

    sync_prod, sync_im, sync_fm = construct_synchronous_product(pn1, im1, fm1, pn2, im2, fm2, SKIP)
    save_vis_petri_net(sync_prod, sync_im, sync_fm, f'data/viz/sync_product/trees_1_1+1_2.png')

    result = unfold_sync_net(sync_prod, sync_im, sync_fm)
    print(f'time taken: {round(result["time_taken"] * 1000, 3)} ms')
    print(f'alignment costs: {result["costs"]}')


@click.group()
def cli():
    pass


cli.add_command(compute_unfolding_based_alignments, "unfolding-based-alignments")
cli.add_command(compute_unfolding_based_alignments_from_trees, "unfolding-based-alignments-trees")

if __name__ == '__main__':
    cli()
