"""Allocation engine: greedy warm start + OR-Tools CP-SAT optimisation.

Pipeline (matches the synopsis):
  1. suitability scores for every faculty-course pair
  2. greedy initial assignment + heuristic re-balancing
  3. CP-SAT enforces hard constraints and optimises
        maximise  total suitability  -  balance_weight * (max load - min load)
  4. if infeasible, report which constraint groups conflict
"""
import os
import time

from ortools.sat.python import cp_model

from .constraints import GROUP_LABELS, check_allocation
from .model import build_maps
from .scoring import build_suitability
from .utils import fmt_slots

GROUPS = list(GROUP_LABELS)
HOUR_SCALE = 10      # hours and loads are multiplied by 10 to stay integral
SCORE_SCALE = 10     # suitability 0-100 -> 0-1000


# ---------------------------------------------------------------- heuristics
def greedy_initial(fac, crs, suit, settings, locked=None, rebalance=True):
    assign = dict(locked or {})
    loads = {f: 0.0 for f in fac}
    hours = {f: 0.0 for f in fac}
    used = {f: set() for f in fac}

    def place(code, f):
        assign[code] = f
        loads[f] += crs[code]["load"]
        hours[f] += crs[code]["hours"]
        used[f] |= crs[code]["slots"]

    def unplace(code):
        f = assign.pop(code)
        loads[f] -= crs[code]["load"]
        hours[f] -= crs[code]["hours"]
        used[f] -= crs[code]["slots"]

    def can_take(f, code):
        c, i = crs[code], fac[f]
        if c["slots"] & i["blocked"] or c["slots"] & used[f]:
            return False
        return i["max"] is None or hours[f] + c["hours"] <= i["max"] + 1e-9

    for code, f in list((locked or {}).items()):
        assign.pop(code, None)
        place(code, f)

    target = max(sum(c["load"] for c in crs.values()) / max(len(fac), 1), 1e-9)

    def free_count(code):
        return sum(1 for f in fac if not (crs[code]["slots"] & fac[f]["blocked"]))

    todo = sorted((c for c in crs if c not in assign), key=lambda c: (free_count(c), -crs[c]["load"]))
    for code in todo:
        pool = [f for f in fac if can_take(f, code)] or list(fac)
        best = max(pool, key=lambda f: suit[f, code]["score"]
                   - 100.0 * (loads[f] + crs[code]["load"]) / target)
        place(code, best)

    if rebalance:
        threshold = float(settings.get("rebalance_threshold", 1.0))
        locked_codes = set(locked or {})
        for _ in range(200):
            fmax = max(loads, key=loads.get)
            fmin = min(loads, key=loads.get)
            gap = loads[fmax] - loads[fmin]
            if gap <= threshold:
                break
            moved = False
            movable = sorted((c for c, f in assign.items() if f == fmax and c not in locked_codes),
                             key=lambda c: -crs[c]["load"])
            for code in movable:
                if crs[code]["load"] >= gap:
                    continue
                min_h = fac[fmax]["min"]
                if min_h is not None and hours[fmax] - crs[code]["hours"] < min_h - 1e-9:
                    continue
                if can_take(fmin, code):
                    unplace(code)
                    place(code, fmin)
                    moved = True
                    break
            if not moved:
                break
    return assign


# ------------------------------------------------------------------ CP-SAT
def _eligible(fac, crs, relax, locked):
    elig = {}
    for code, c in crs.items():
        if code in locked and locked[code] in fac:
            elig[code] = [locked[code]]
            continue
        elig[code] = [f for f, i in fac.items()
                      if "availability" in relax or not (c["slots"] & i["blocked"])]
    return elig


def _run_cp(fac, crs, suit, settings, relax, locked, time_limit, hint=None, optimise=True):
    """Return (status_name, assignment | None, objective | None)."""
    elig = _eligible(fac, crs, relax, locked)
    if any(not v for v in elig.values()):
        return "INFEASIBLE", None, None

    m = cp_model.CpModel()
    x = {}
    for code, flist in elig.items():
        for f in flist:
            x[f, code] = m.NewBoolVar(f"x_{f}_{code}")
        m.AddExactlyOne(x[f, code] for f in flist)

    if "clash" not in relax:
        for f in fac:
            by_slot = {}
            for code in crs:
                if (f, code) in x:
                    for s in crs[code]["slots"]:
                        by_slot.setdefault(s, []).append(x[f, code])
            for terms in by_slot.values():
                if len(terms) > 1:
                    m.AddAtMostOne(terms)

    load_int = {c: int(round(crs[c]["load"] * HOUR_SCALE)) for c in crs}
    hour_int = {c: int(round(crs[c]["hours"] * HOUR_SCALE)) for c in crs}
    total_load = max(sum(load_int.values()), 1)
    min_l = m.NewIntVar(0, total_load, "min_load")
    max_l = m.NewIntVar(0, total_load, "max_load")

    for f, info in fac.items():
        vars_f = [(code, x[f, code]) for code in crs if (f, code) in x]
        if not vars_f:
            if "hours_min" not in relax and info["min"] and info["min"] > 0:
                return "INFEASIBLE", None, None
            m.Add(min_l <= 0)
            continue
        hrs = sum(hour_int[c] * v for c, v in vars_f)
        if "hours_max" not in relax and info["max"] is not None:
            m.Add(hrs <= int(round(info["max"] * HOUR_SCALE)))
        if "hours_min" not in relax and info["min"] is not None:
            m.Add(hrs >= int(round(info["min"] * HOUR_SCALE)))
        load = sum(load_int[c] * v for c, v in vars_f)
        m.Add(load >= min_l)
        m.Add(load <= max_l)

    if optimise:
        score_terms = [int(round(suit[f, c]["score"] * SCORE_SCALE)) * v for (f, c), v in x.items()]
        bal = int(round(float(settings.get("balance_weight", 10.0)) * SCORE_SCALE))
        m.Maximize(sum(score_terms) - bal * (max_l - min_l))

    if hint:
        for (f, code), v in x.items():
            m.AddHint(v, 1 if hint.get(code) == f else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_workers = max(1, min(8, os.cpu_count() or 1))
    solver.parameters.random_seed = 7
    if optimise:
        solver.parameters.relative_gap_limit = 0.005
    status = solver.Solve(m)
    name = solver.StatusName(status)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assign = {code: f for (f, code), v in x.items() if solver.Value(v)}
        return name, assign, (solver.ObjectiveValue() if optimise else None)
    return name, None, None


def diagnose(fac, crs, suit, settings, locked):
    """Explain why the problem is infeasible (list of human-readable lines)."""
    msgs = []
    for code, c in crs.items():
        if not any(not (c["slots"] & i["blocked"]) for i in fac.values()):
            msgs.append(f"Nobody is free for {code} ({c['name']}) at {fmt_slots(c['slots'])}: "
                        f"every faculty member has at least one of those slots blocked.")

    total = sum(c["hours"] for c in crs.values())
    cap_max = sum(i["max"] for i in fac.values() if i["max"] is not None)
    cap_min = sum(i["min"] for i in fac.values() if i["min"] is not None)
    if total > cap_max + 1e-9:
        msgs.append(f"Total course hours ({total:g}) exceed the combined maximum hours of all "
                    f"faculty ({cap_max:g}).")
    if total < cap_min - 1e-9:
        msgs.append(f"Total course hours ({total:g}) are below the combined minimum hours of all "
                    f"faculty ({cap_min:g}).")

    if locked:
        st, a, _ = _run_cp(fac, crs, suit, settings, set(), {}, 5, optimise=False)
        if a is not None:
            msgs.append("The manual overrides you keep locked conflict with the hard constraints. "
                        "Untick 'keep manual overrides' or change the override.")

    single = []
    for g in GROUPS:
        st, a, _ = _run_cp(fac, crs, suit, settings, {g}, locked, 5, optimise=False)
        if a is not None:
            single.append(g)
    if single:
        msgs.append("Relaxing any ONE of these makes a solution possible: "
                    + ", ".join(GROUP_LABELS[g] for g in single) + ".")
    elif not msgs:
        for i, g1 in enumerate(GROUPS):
            for g2 in GROUPS[i + 1:]:
                st, a, _ = _run_cp(fac, crs, suit, settings, {g1, g2}, locked, 5, optimise=False)
                if a is not None:
                    msgs.append(f"Relaxing both '{GROUP_LABELS[g1]}' and '{GROUP_LABELS[g2]}' "
                                f"makes a solution possible.")
                    return msgs
        msgs.append("Several constraint groups conflict together; review faculty hours and "
                    "availability against the course list.")
    return msgs


# --------------------------------------------------------------------- API
def allocate(faculty_df, courses_df, prefs_df, past_df, settings,
             locked=None, relax=(), time_limit=None):
    t0 = time.time()
    relax = set(relax)
    fac, crs = build_maps(faculty_df, courses_df, settings)
    suit = build_suitability(fac, crs, prefs_df, past_df, settings)
    locked = {c: f for c, f in (locked or {}).items() if c in crs and f in fac}
    limit = float(time_limit or settings.get("solver_seconds", 15))

    greedy = greedy_initial(fac, crs, suit, settings, locked)
    status, assign, obj = _run_cp(fac, crs, suit, settings, relax, locked, limit, hint=greedy)

    result = {"status": status, "assignment": {}, "objective": obj, "diagnosis": [],
              "note": "", "relaxed": sorted(relax), "locked": sorted(locked)}
    if assign is not None:
        result["assignment"] = assign
    elif status == "INFEASIBLE":
        result["diagnosis"] = diagnose(fac, crs, suit, settings, locked)
    else:  # UNKNOWN / MODEL_INVALID: fall back to the heuristic answer
        result["assignment"] = greedy
        result["status"] = "HEURISTIC"
        result["note"] = ("The solver found no solution within the time limit; showing the "
                          "heuristic assignment instead. Increase the time limit and retry.")
    result["violations"] = (check_allocation(result["assignment"], fac, crs, relax)
                            if result["assignment"] else [])
    result["runtime"] = round(time.time() - t0, 2)
    return result
