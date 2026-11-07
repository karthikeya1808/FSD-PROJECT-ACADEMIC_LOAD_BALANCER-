"""Exportable reports (PDF / Excel)."""
from datetime import datetime

import streamlit as st

from core.reports import excel_bytes, pdf_bytes

from .common import goto, load_all, violations_df
from .dashboard import get_report


def render():
    st.header("Export Reports")
    ctx = load_all()
    if not ctx.assign:
        st.info("Generate an allocation first.")
        st.button("Go to Generate Allocation", on_click=goto, args=("Allocate",), key="ex_go_alloc")
        return

    loads, alloc, viol, sm = get_report(ctx)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    st.write(f"Report covers **{sm['assigned']} / {sm['courses']}** courses, "
             f"balance score **{sm['balance_score']:.0f}/100**, **{sm['violations']}** hard violation(s).")
    vdf = violations_df(viol)
    c1, c2 = st.columns(2)
    c1.download_button("Download Excel report", excel_bytes(sm, loads, alloc, vdf),
                       file_name=f"allocation_{stamp}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key="dl_xlsx")
    c2.download_button("Download PDF report", pdf_bytes(sm, loads, alloc, vdf),
                       file_name=f"allocation_{stamp}.pdf", mime="application/pdf", key="dl_pdf")
    st.caption("Both reports contain the summary indicators, faculty load, course allocation and any violations.")
