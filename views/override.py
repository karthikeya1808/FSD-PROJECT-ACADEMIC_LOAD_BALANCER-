"""Manual Override module: change an assignment and re-check constraints instantly."""
import streamlit as st

from core import db
from core.constraints import check_allocation
from core.metrics import faculty_load_table

from .common import goto, load_all


def render():
    st.header("Manual Override")
    ctx = load_all()
    if not ctx.assign:
        st.info("Generate an allocation first.")
        st.button("Go to Generate Allocation", on_click=goto, args=("Allocate",), key="ov_go_alloc")
        return

    codes = list(ctx.crs)
    code = st.selectbox("Course", codes, format_func=lambda c: f"{c} - {ctx.crs[c]['name']}", key="ov_course")
    current = ctx.assign.get(code)
    loads = faculty_load_table(ctx.assign, ctx.fac, ctx.crs, ctx.settings).set_index("fid")

    def label(f):
        s = ctx.suit[f, code]
        tag = "  [current]" if f == current else ""
        return (f"{ctx.fac[f]['name']} ({f}) - load {loads.at[f, 'load']:g}, "
                f"match {s['expertise'] * 100:.0f}%, suitability {s['score']:.0f}{tag}")

    options = list(ctx.fac)
    new = st.selectbox("Assign to", options, index=options.index(current) if current in options else 0,
                       format_func=label, key=f"ov_new_{code}")

    if new == current:
        st.info("This is already the assigned faculty member. Pick someone else to preview a change.")
        return

    trial = dict(ctx.assign)
    trial[code] = new
    before = check_allocation(ctx.assign, ctx.fac, ctx.crs)
    after = check_allocation(trial, ctx.fac, ctx.crs)
    before_msgs = {v["message"] for v in before}
    after_msgs = {v["message"] for v in after}
    introduced = [v for v in after if v["message"] not in before_msgs]
    resolved = [v for v in before if v["message"] not in after_msgs]
    loads_after = faculty_load_table(trial, ctx.fac, ctx.crs, ctx.settings).set_index("fid")

    st.subheader("Impact")
    c1, c2, c3 = st.columns(3)
    for col, f, role in ((c1, current, "Currently"), (c2, new, "Would receive")):
        col.metric(f"{role}: {ctx.fac[f]['name']}",
                   f"{loads_after.at[f, 'load']:g} load",
                   delta=f"{loads_after.at[f, 'load'] - loads.at[f, 'load']:+g}", delta_color="off")
        col.caption(f"{loads_after.at[f, 'hours']:g} h/week, allowed "
                    f"{ctx.fac[f]['min']:g}-{ctx.fac[f]['max']:g}" if ctx.fac[f]["min"] is not None
                    else f"{loads_after.at[f, 'hours']:g} h/week")
    gap_b = loads["load"].max() - loads["load"].min()
    gap_a = loads_after["load"].max() - loads_after["load"].min()
    c3.metric("Balance gap", f"{gap_a:g}", delta=f"{gap_a - gap_b:+g}", delta_color="inverse")

    s_old, s_new = ctx.suit[current, code]["score"], ctx.suit[new, code]["score"]
    st.caption(f"Suitability for {code}: {s_old:.0f} -> {s_new:.0f} "
               f"(expertise match {ctx.suit[new, code]['expertise'] * 100:.0f}%).")

    if introduced:
        st.error(f"This change would introduce {len(introduced)} hard-constraint violation(s):")
        for v in introduced:
            st.write(f"- {v['message']}")
    else:
        st.success("No new hard-constraint violations.")
    if resolved:
        st.info(f"It would also resolve {len(resolved)} existing violation(s).")
    if after and not introduced:
        st.caption(f"{len(after)} violation(s) from the current allocation remain.")

    if st.button("Apply override", type="primary", key="ov_apply"):
        manual = set(ctx.manual) | {code}
        db.save_assignment(trial, manual, ctx.suit)
        st.toast(f"{code} reassigned to {ctx.fac[new]['name']}.")
        st.rerun()
    st.caption("Tip: tick 'Keep manual overrides locked' on the Generate Allocation page to let the solver "
               "re-balance everything else around your change.")
