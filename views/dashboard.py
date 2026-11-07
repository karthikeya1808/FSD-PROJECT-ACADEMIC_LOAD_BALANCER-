"""Reporting Dashboard."""
import plotly.graph_objects as go
import streamlit as st

from core.constraints import check_allocation
from core.metrics import allocation_table, faculty_load_table, summary

from .common import goto, load_all, violations_df

TYPE_COLORS = {"load_theory": "#2F5597", "load_lab": "#ED7D31", "load_tutorial": "#70AD47"}
TYPE_LABELS = {"load_theory": "Theory", "load_lab": "Lab", "load_tutorial": "Tutorial"}


def get_report(ctx):
    """Everything the dashboard and the exports need."""
    loads = faculty_load_table(ctx.assign, ctx.fac, ctx.crs, ctx.settings)
    alloc = allocation_table(ctx.assign, ctx.fac, ctx.crs, ctx.suit)
    viol = check_allocation(ctx.assign, ctx.fac, ctx.crs)
    return loads, alloc, viol, summary(loads, ctx.assign, ctx.fac, ctx.crs, ctx.suit, viol)


def render():
    st.header("Dashboard")
    ctx = load_all()
    if not ctx.assign:
        st.info("No allocation yet. Generate one first.")
        st.button("Go to Generate Allocation", on_click=goto, args=("Allocate",), key="go_alloc")
        return

    loads, alloc, viol, sm = get_report(ctx)

    # --- summary indicators
    c = st.columns(6)
    c[0].metric("Average load", sm["avg_load"], help="Weighted hours per faculty member.")
    c[1].metric("Load variance", sm["load_variance"], help="Lower = more even.")
    c[2].metric("Balance score", f"{sm['balance_score']:.0f}/100",
                help="100 x (1 - (max load - min load) / max load). 100 = perfectly even.")
    c[3].metric("Expertise match", "n/a" if sm["expertise_match_rate"] is None else f"{sm['expertise_match_rate']:.0f}%")
    c[4].metric("Preferences honoured",
                "n/a" if sm["pref_satisfaction"] is None else f"{sm['pref_satisfaction']:.0f}%",
                help="Share of faculty (who gave preferences) who got at least one preferred course.")
    c[5].metric("Hard violations", sm["violations"], help="Target: 0.")

    lr = ctx.last_run
    if lr and lr.get("runtime") is not None:
        manual_min = ctx.settings["manual_baseline_minutes"]
        saved = 100 * (1 - (lr["runtime"] / 60) / manual_min)
        st.caption(f"Time saved: allocation took {lr['runtime']} s versus about {manual_min:.0f} min "
                   f"manually (~{saved:.1f}% faster). Solver status: {lr['status']}.")
    if ctx.manual:
        st.caption(f"{len(ctx.manual)} course(s) manually overridden: {', '.join(sorted(ctx.manual))}.")

    # --- alerts
    st.subheader("Alerts")
    flagged = loads[loads["status"] != "OK"]
    if flagged.empty:
        st.success("No overloaded or underloaded faculty.")
    for _, r in flagged.iterrows():
        msg = (f"**{r['name']}** ({r['fid']}): {r['status']} - load {r['load']:g}, "
               f"{r['hours']:g} h/week (allowed {r['min_hours']:g}-{r['max_hours']:g}).")
        (st.error if "hours" in r["status"] else st.warning)(msg)
    if viol:
        st.error(f"{len(viol)} hard-constraint violation(s):")
        st.dataframe(violations_df(viol), hide_index=True)

    # --- charts
    st.subheader("Faculty-wise load")
    left, right = st.columns(2)
    names = [f"{r.name} ({r.fid})" for r in loads.itertuples()]
    fig = go.Figure()
    for col, color in TYPE_COLORS.items():
        fig.add_bar(x=names, y=loads[col], name=TYPE_LABELS[col], marker_color=color)
    fig.add_hline(y=sm["avg_load"], line_dash="dash", line_color="#444",
                  annotation_text=f"average {sm['avg_load']}")
    fig.update_layout(barmode="stack", title="Weighted load by course type", height=380,
                      margin=dict(t=50, b=10), yaxis_title="Load", legend_orientation="h",
                      legend_y=-0.35)
    left.plotly_chart(fig)

    fig2 = go.Figure()
    fig2.add_bar(x=names, y=loads["hours"], name="Assigned hours", marker_color="#2F5597")
    fig2.add_scatter(x=names, y=loads["min_hours"], mode="markers", name="Min allowed",
                     marker=dict(symbol="triangle-up", size=10, color="#70AD47"))
    fig2.add_scatter(x=names, y=loads["max_hours"], mode="markers", name="Max allowed",
                     marker=dict(symbol="triangle-down", size=10, color="#C00000"))
    fig2.update_layout(title="Weekly hours vs allowed range", height=380, margin=dict(t=50, b=10),
                       yaxis_title="Hours / week", legend_orientation="h", legend_y=-0.35)
    right.plotly_chart(fig2)

    st.dataframe(
        loads[["fid", "name", "designation", "courses", "hours", "load", "load_theory", "load_lab",
               "load_tutorial", "status"]],
        hide_index=True,
        column_config={"fid": "ID", "name": "Name", "designation": "Designation", "courses": "Courses",
                       "hours": "Hours", "load": "Load", "load_theory": "Theory load",
                       "load_lab": "Lab load", "load_tutorial": "Tutorial load", "status": "Status"})

    # --- allocation table
    st.subheader("Course allocation")
    pick = st.multiselect("Filter by faculty", list(alloc["faculty"].unique()))
    view = alloc[alloc["faculty"].isin(pick)] if pick else alloc
    view = view.assign(manual=view["code"].map(lambda c: "yes" if c in ctx.manual else ""))
    st.dataframe(
        view, hide_index=True,
        column_config={
            "code": "Code", "course": "Course", "type": "Type", "hours": "Hours",
            "required_skill": "Required skill", "faculty_id": "Faculty ID", "faculty": "Faculty",
            "expertise_match": st.column_config.ProgressColumn("Expertise match %", min_value=0, max_value=100, format="%d"),
            "suitability": st.column_config.ProgressColumn("Suitability", min_value=0, max_value=100, format="%.1f"),
            "manual": "Manual",
        })
    st.button("Export reports", on_click=goto, args=("Export Reports",), key="go_export")
