"""Allocation Engine + Constraint Solver page."""
import streamlit as st

from core import db
from core.constraints import GROUP_LABELS
from core.solver import allocate
from core.validation import has_errors, validate_inputs
from datetime import datetime

from .common import goto, load_all


def render():
    st.header("Generate Allocation")
    ctx = load_all()
    issues = validate_inputs(ctx.faculty, ctx.courses, ctx.prefs, ctx.past, ctx.settings)
    errs = [i for i in issues if i["level"] == "error"]
    if errs:
        st.error("Fix these data problems first (Data Management page):")
        for i in errs:
            st.write(f"- {i['message']}")
    elif issues:
        with st.expander(f"{len(issues)} data warning(s)"):
            for i in issues:
                st.write(f"- {i['message']}")

    st.markdown(
        "The engine scores every faculty-course pair, builds a heuristic starting assignment, then the "
        "OR-Tools CP-SAT solver enforces the hard constraints (no clashes, availability, min/max hours, "
        "one faculty per course) while **maximising expertise match** and **minimising the load gap**."
    )

    c1, c2 = st.columns(2)
    balance = c1.slider(
        "Load balance importance", 0.0, 30.0, float(ctx.settings["balance_weight"]), 0.5,
        help="Higher = fairer loads, lower = better expertise match. Penalty per 0.1 weighted hour of "
             "(max load - min load), compared with a 0-100 suitability score per course.")
    seconds = c2.slider("Solver time limit (seconds)", 5, 120, int(ctx.settings["solver_seconds"]), 5)

    keep_manual = False
    if ctx.manual:
        keep_manual = st.checkbox(
            f"Keep my {len(ctx.manual)} manual override(s) locked and optimise the rest around them",
            value=True)
    relax = st.multiselect(
        "Relax constraint groups (only use if the solver reports a conflict)",
        options=list(GROUP_LABELS), format_func=lambda g: GROUP_LABELS[g])

    if st.button("Generate Allocation", type="primary", disabled=bool(errs), key="btn_generate"):
        settings = dict(ctx.settings, balance_weight=balance, solver_seconds=seconds)
        db.save_settings({"balance_weight": balance, "solver_seconds": seconds})
        locked = {c: ctx.assign[c] for c in ctx.manual} if keep_manual else {}
        with st.spinner("Optimising..."):
            res = allocate(ctx.faculty, ctx.courses, ctx.prefs, ctx.past, settings,
                           locked=locked, relax=relax, time_limit=seconds)
        st.session_state["last_result"] = res
        if res["assignment"]:
            manual = set(res["locked"])
            db.save_assignment(res["assignment"], manual, ctx.suit)
            db.save_last_run({
                "status": res["status"], "runtime": res["runtime"], "relaxed": res["relaxed"],
                "violations": len(res["violations"]), "note": res["note"],
                "at": datetime.now().isoformat(timespec="seconds"),
            })

    res = st.session_state.get("last_result")
    if not res:
        return
    if res["status"] == "INFEASIBLE":
        st.error("No allocation satisfies all the hard constraints.")
        for line in res["diagnosis"]:
            st.write(f"- {line}")
        st.info("Relax one of the suggested constraint groups above and generate again, or fix the data.")
        return
    if res["status"] == "HEURISTIC":
        st.warning(res["note"])
    elif res["status"] == "OPTIMAL":
        st.success(f"Optimal allocation found in {res['runtime']} s.")
    else:
        st.success(f"Good allocation found in {res['runtime']} s (solver stopped at its time limit or "
                   "gap target; it may not be provably optimal).")
    if res["violations"]:
        st.warning(f"{len(res['violations'])} hard-constraint violation(s) remain "
                   f"(relaxed: {', '.join(res['relaxed']) or 'none'}). See the Dashboard.")
    st.button("View the dashboard", on_click=goto, args=("Dashboard",), key="go_dash")
