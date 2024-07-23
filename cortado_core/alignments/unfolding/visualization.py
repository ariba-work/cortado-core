import graphviz

from cortado_core.alignments.unfolding.obj.branching_process import BranchingProcess
from cortado_core.alignments.unfolding.utils import UnfoldingAlignmentResult, _get_type, _get_move_label
from cortado_core.utils.constants import DependencyTypes


def draw_unfolded_alignment(alignment: UnfoldingAlignmentResult, file_path: str, label: str = None):
    """
    Draw just the unfolded alignment. It is an occurrence net with events, conditions and arcs.
    Args:
        label (): extra information to write
        alignment (): the alignment (occurrence net) to draw
        file_path (): file path to save the rendered png image. File path includes the file name without an extension

    Returns:
        void
    """

    g = graphviz.Digraph('unfolding', graph_attr={'rankdir': 'LR'})

    for event in alignment.final_events:
        add_node_and_edges_viz(g, event, {})

    g.attr(overlap='false')
    g.attr(label=label)
    g.attr(fontsize='12')

    g.render(filename=file_path, view=False, format="png")


def __get_move_name(move):
    if isinstance(move, BranchingProcess.OccurrenceNet.Event):
        return f'e{move.name}'
    elif isinstance(move, BranchingProcess.OccurrenceNet.Condition):
        return f'c{move.name}'
    else:
        return 'None'


def _get_move_color(move):
    return _get_color_by_type(_get_type(move))


def _get_color_by_type(dep_type: str):
    if dep_type == DependencyTypes.MODEL.value:
        return 'darkturquoise'
    elif dep_type == DependencyTypes.LOG.value:
        return 'orange'
    elif dep_type == DependencyTypes.SYNCHRONOUS.value:
        return 'orange:darkturquoise'
    else:
        return 'gray'


def add_node_and_edges_viz(g, event, edges: dict = None):
    g.node(f'e{event.name}', label=f'e{event.name}/{_get_move_label(event.mapped_transition.label)}',
           fillcolor=_get_move_color(event.mapped_transition.name),
           style="filled", orientation="270", shape='house')

    for condition in event.preset:
        c_pre = list(condition.preset)[0] if len(condition.preset) > 0 else None
        if c_pre:
            source = __get_move_name(c_pre)
            target = __get_move_name(event)
            color = _get_move_color(condition.mapped_place.name)
            if (source, target, color) not in edges.keys():
                edges[(source, target, color)] = True
                g.edge(source, target, color=color)
            add_node_and_edges_viz(g, c_pre, edges)
