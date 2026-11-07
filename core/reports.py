"""Excel / PDF exports and the import template."""
from datetime import datetime
from io import BytesIO

import pandas as pd
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .sample_data import sample_frames

NAVY = "1F3864"

SUMMARY_LABELS = [
    ("assigned", "Courses assigned"), ("avg_load", "Average load (weighted hours)"),
    ("load_variance", "Load variance"), ("load_std", "Load std. deviation"),
    ("balance_gap", "Balance gap (max - min load)"), ("balance_score", "Balance score (0-100)"),
    ("expertise_match_rate", "Expertise match rate (%)"),
    ("pref_satisfaction", "Preference satisfaction (%)"), ("violations", "Hard-constraint violations"),
]


def summary_rows(summary: dict):
    rows = []
    for key, label in SUMMARY_LABELS:
        v = summary.get(key)
        if key == "assigned":
            v = f"{summary['assigned']} / {summary['courses']}"
        rows.append((label, "n/a" if v is None else v))
    return rows


def _pretty(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=lambda c: c.replace("_", " ").title())


# ---------------------------------------------------------------------- Excel
def excel_bytes(summary: dict, loads_df, alloc_df, viol_df) -> bytes:
    buf = BytesIO()
    viol = viol_df if len(viol_df) else pd.DataFrame({"message": ["No hard-constraint violations."]})
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(summary_rows(summary), columns=["Metric", "Value"]).to_excel(
            xw, sheet_name="Summary", index=False)
        _pretty(loads_df).to_excel(xw, sheet_name="Faculty Load", index=False)
        _pretty(alloc_df).to_excel(xw, sheet_name="Allocation", index=False)
        _pretty(viol).to_excel(xw, sheet_name="Violations", index=False)

        head_fill = PatternFill("solid", fgColor=NAVY)
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = head_fill
                cell.alignment = Alignment(vertical="center")
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 60)

        ws = xw.book["Faculty Load"]
        headers = [c.value for c in ws[1]]
        if "Load" in headers and "Name" in headers and ws.max_row > 1:
            chart = BarChart()
            chart.type = "col"
            chart.title = "Weighted teaching load per faculty"
            chart.y_axis.title = "Load"
            lc = headers.index("Load") + 1
            nc = headers.index("Name") + 1
            chart.add_data(Reference(ws, min_col=lc, min_row=1, max_row=ws.max_row), titles_from_data=True)
            chart.set_categories(Reference(ws, min_col=nc, min_row=2, max_row=ws.max_row))
            chart.height, chart.width = 9, 20
            ws.add_chart(chart, f"A{ws.max_row + 3}")
    return buf.getvalue()


def template_workbook() -> bytes:
    """Excel workbook with the four importable sheets, pre-filled with demo data."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sample_frames().items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.book[name]
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=NAVY)
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 50)
    return buf.getvalue()


# ------------------------------------------------------------------------ PDF
def _fmt(v):
    if isinstance(v, float):
        return "" if v != v else f"{v:.1f}".rstrip("0").rstrip(".")
    return "" if v is None else str(v)


def _table(df: pd.DataFrame, widths, small: ParagraphStyle):
    head = ParagraphStyle("head", parent=small, textColor=colors.white)
    data = [[Paragraph(f"<b>{c.replace('_', ' ').title()}</b>", head) for c in df.columns]]
    for row in df.itertuples(index=False):
        data.append([Paragraph(_fmt(v), small) for v in row])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + NAVY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5FA")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C2D0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def pdf_bytes(summary: dict, loads_df, alloc_df, viol_df, title="Academic Load Balancer - Allocation Report") -> bytes:
    buf = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm, title=title)
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10)
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=colors.HexColor("#" + NAVY), fontSize=18)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#" + NAVY))
    width = page[0] - 28 * mm

    story = [Paragraph(title, h1),
             Paragraph(f"Generated {datetime.now():%d %b %Y, %H:%M}", styles["Normal"]), Spacer(1, 6)]

    story.append(Paragraph("Summary", h2))
    srows = [[Paragraph(f"<b>{k}</b>", small), Paragraph(_fmt(v), small)] for k, v in summary_rows(summary)]
    st = Table(srows, colWidths=[width * 0.4, width * 0.2])
    st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C2D0")),
                            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5FA"))]))
    story += [st, Spacer(1, 10)]

    if len(loads_df):
        story.append(Paragraph("Weighted load per faculty", h2))
        d = Drawing(width, 170)
        ch = VerticalBarChart()
        ch.x, ch.y, ch.width, ch.height = 40, 30, width - 60, 125
        ch.data = [[float(v) for v in loads_df["load"]]]
        ch.categoryAxis.categoryNames = list(loads_df["fid"])
        ch.valueAxis.valueMin = 0
        ch.bars[0].fillColor = colors.HexColor("#2F5597")
        ch.categoryAxis.labels.fontSize = 8
        ch.valueAxis.labels.fontSize = 8
        d.add(ch)
        story += [d, Spacer(1, 6)]

        cols = ["fid", "name", "designation", "courses", "hours", "load", "min_hours", "max_hours", "status"]
        story.append(_table(loads_df[cols], [width * w for w in (.06, .2, .17, .07, .07, .07, .08, .08, .2)], small))

    story += [Spacer(1, 12), Paragraph("Course allocation", h2)]
    cols = ["code", "course", "type", "hours", "faculty_id", "faculty", "expertise_match", "suitability"]
    story.append(_table(alloc_df[cols], [width * w for w in (.08, .28, .08, .06, .08, .2, .11, .11)], small))

    story += [Spacer(1, 12), Paragraph("Hard-constraint violations", h2)]
    if len(viol_df):
        story.append(_table(viol_df[["type", "faculty", "course", "message"]],
                            [width * w for w in (.12, .08, .12, .68)], small))
    else:
        story.append(Paragraph("None - all hard constraints are satisfied.", styles["Normal"]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(page[0] - 14 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
