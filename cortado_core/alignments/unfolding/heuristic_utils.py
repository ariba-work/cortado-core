import sys

import numpy as np
from cvxopt import matrix
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.objects.petri_net.utils.incidence_matrix import IncidenceMatrix
from pm4py.util.lp import solver as lp_solver


def vectorize_initial_final_cost(incidence_matrix: IncidenceMatrix, initial_marking: Marking, final_marking: Marking,
                                 cost_function: dict[PetriNet.Transition, int]):
    ini_vec = incidence_matrix.encode_marking(initial_marking)
    fini_vec = incidence_matrix.encode_marking(final_marking)
    cost_vec = [0] * len(cost_function)
    for t, costs in cost_function.items():
        cost_vec[incidence_matrix.transitions[t]] = costs
    return ini_vec, fini_vec, cost_vec


def vectorize_matrices(incidence_matrix: IncidenceMatrix, sync_net: PetriNet):
    a_matrix = np.asmatrix(incidence_matrix.a_matrix).astype(np.float64)
    g_matrix = -np.eye(len(sync_net.transitions))
    h_cvx = np.matrix(np.zeros(len(sync_net.transitions))).transpose()

    a_matrix = matrix(a_matrix)
    g_matrix = matrix(g_matrix)
    h_cvx = matrix(h_cvx)

    return a_matrix, g_matrix, h_cvx


def derive_heuristic(incidence_matrix: IncidenceMatrix, cost_vec, x: list[float], t: PetriNet.Transition,
                     h: int):
    x_prime = x.copy()
    x_prime[incidence_matrix.transitions[t]] -= 1
    return max(0, h - cost_vec[incidence_matrix.transitions[t]]), x_prime


def is_solution_feasible(x: list[float]):
    for v in x:
        if v < -0.001:
            return False
    return True


def compute_exact_heuristic(sync_net, a_matrix, h_cvx, g_matrix, cost_vec, incidence_matrix, marking, fin_vec):
    # compute diff marking
    m_vec = incidence_matrix.encode_marking(marking)
    b_term = [i - j for i, j in zip(fin_vec, m_vec)]
    b_term = np.matrix([x * 1.0 for x in b_term]).transpose()
    b_term = matrix(b_term)

    sol = lp_solver.apply(cost_vec, g_matrix, h_cvx, a_matrix, b_term, parameters={"solver": "glpk"})
    prim_obj = lp_solver.get_prim_obj_from_sol(sol)
    points = lp_solver.get_points_from_sol(sol)

    prim_obj = prim_obj if prim_obj is not None else sys.maxsize
    points = points if points is not None else [0.0] * len(sync_net.transitions)

    return prim_obj, points
