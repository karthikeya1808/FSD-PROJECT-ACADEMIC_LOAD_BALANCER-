"""Data Management module: faculty, courses, preferences, history, rules, import/reset."""
import pandas as pd
import streamlit as st

from core import db
from core.config import (COURSE_TYPES, DEFAULT_SETTINGS, DESIGNATION_HOURS, DESIGNATIONS, TABLES)
from core.reports import template_workbook
from core.sample_data import load_sample_into_db
from core.utils import invalid_slots, is_blank, to_float
from core.validation import has_errors, validate_inputs

from .common import load_all


# ------------------------------------------------------------------ helpers
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df.reset_index(drop=True)
    for c in df.columns:
        df[c] = df[c].map(lambda v: v.strip() if isinstance(v, str) else v)
    keep = [not all(is_blank(v) for v in row) for row in df.itertuples(index=False)]
    return df[keep].reset_index(drop=True)


def _version(table: str) -> int:
    return st.session_state.setdefault(f"ver_{table}", 0)


def _bump(table: str) -> None:
    st.session_state[f"ver_{table}"] = _version(table) + 1


def _save_faculty(edited: pd.DataFrame):
    df = _clean(edited)
    errors = []
    for i, r in df.iterrows():
        label = f"Row {i + 1}"
        if is_blank(r["fid"]) or is_blank(r["name"]):
            errors.append(f"{label}: id and name are required.")
            continue
        d = r["designation"]
        if is_blank(r["min_hours"]) and d in DESIGNATION_HOURS:
            df.at[i, "min_hours"] = DESIGNATION_HOURS[d][0]
        if is_blank(r["max_hours"]) and d in DESIGNATION_HOURS:
            df.at[i, "max_hours"] = DESIGNATION_HOURS[d][1]
        bad = invalid_slots(r["unavailable_slots"])
        if bad:
            errors.append(f"{r['fid']}: invalid slot(s) {', '.join(bad)}.")
    dup = df["fid"][df["fid"].duplicated()].tolist()
    if dup:
        errors.append(f"Duplicate faculty id(s): {', '.join(map(str, dup))}")
    return df, errors


def _save_courses(edited: pd.DataFrame):
    df = _clean(edited)
    errors = []
    for i, r in df.iterrows():
        if is_blank(r["code"]) or is_blank(r["name"]):
            errors.append(f"Row {i + 1}: code and name are required.")
            continue
        if is_blank(r["type"]) or str(r["type"]).lower() not in COURSE_TYPES:
            errors.append(f"{r['code']}: choose a type ({', '.join(COURSE_TYPES)}).")
        h = to_float(r["weekly_hours"])
        if h is None or h <= 0:
            errors.append(f"{r['code']}: weekly hours must be > 0.")
        bad = invalid_slots(r["slots"])
        if bad:
            errors.append(f"{r['code']}: invalid slot(s) {', '.join(bad)}.")
    dup = df["code"][df["code"].duplicated()].tolist()
    if dup:
        errors.append(f"Duplicate course code(s): {', '.join(map(str, dup))}")
    return df, errors


def _save_simple(edited: pd.DataFrame, key_cols):
    df = _clean(edited)
    errors = []
    if df[key_cols].isna().any().any() or (df[key_cols].astype(str).apply(lambda s: s.str.strip() == "")).any().any():
        errors.append("All key columns must be filled in.")
    if df.duplicated(subset=key_cols).any():
        errors.append("Duplicate rows found.")
    return df, errors


def _editor(table, title, columns_cfg, saver, help_text):
    st.caption(help_text)
    df = db.read_table(table)
    edited = st.data_editor(df, num_rows="dynamic", hide_index=True, column_config=columns_cfg,
                            key=f"ed_{table}_{_version(table)}")
    if st.button(f"Save {title}", type="primary", key=f"save_{table}"):
        out, errors = saver(edited)
        if errors:
            for e in errors:
                st.error(e)
        else:
            db.write_table(table, out)
            if table in ("faculty", "courses"):
                db.prune_allocations()
            _bump(table)
            st.toast(f"{title} saved ({len(out)} rows).")
            st.rerun()


# ------------------------------------------------------------------- import
_ALIASES = {
    "id": "fid", "faculty_id": "fid", "facultyid": "fid", "course_code": "code", "course_id": "code",
    "weekly hours": "weekly_hours", "hours": "weekly_hours", "course_type": "type",
    "unavailable": "unavailable_slots", "blocked_slots": "unavailable_slots", "skills": "expertise",
    "pref_rank": "rank", "preference_rank": "rank", "required skill": "required_skill",
    "min": "min_hours", "max": "max_hours",
}


def _normalise(df: pd.DataFrame, table: str):
    df = df.copy()
    df.columns = [_ALIASES.get(str(c).strip().lower().replace(" ", "_"),
                               str(c).strip().lower().replace(" ", "_")) for c in df.columns]
    missing = [c for c in TABLES[table] if c not in df.columns]
    optional = {"faculty": ["min_hours", "max_hours", "unavailable_slots", "expertise"],
                "courses": ["credits", "required_skill", "slots"]}.get(table, [])
    hard_missing = [c for c in missing if c not in optional]
    for c in missing:
        df[c] = None
    return df[TABLES[table]], hard_missing


def _table_for(name: str):
    n = name.lower()
    for key, table in (("faculty", "faculty"), ("course", "courses"), ("pref", "preferences"),
                       ("past", "past_teaching")):
        if key in n:
            return table
    return None


def _read_uploads(files):
    found = {}
    for f in files:
        try:
            if f.name.lower().endswith(".csv"):
                t = _table_for(f.name)
                if t:
                    found[t] = pd.read_csv(f)
                else:
                    st.warning(f"Could not tell which table '{f.name}' is (name it faculty/courses/preferences/past_teaching).")
            else:
                for sheet, df in pd.read_excel(f, sheet_name=None).items():
                    t = _table_for(sheet)
                    if t:
                        found[t] = df
        except Exception as e:  # noqa: BLE001 - show any read error to the user
            st.error(f"Could not read {f.name}: {e}")
    return found


def _import_tab():
    st.markdown("**Import** an Excel workbook (sheets: `faculty`, `courses`, `preferences`, `past_teaching`) "
                "or separate CSV files named after those tables. Imported tables **replace** the current ones.")
    st.download_button("Download Excel template (with demo data)", template_workbook(),
                       file_name="academic_load_balancer_template.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    files = st.file_uploader("Upload .xlsx / .csv", type=["xlsx", "csv"], accept_multiple_files=True,
                             key=f"upload_{_version('import')}")
    if files:
        found = _read_uploads(files)
        ready = {}
        for table, raw in found.items():
            df, missing = _normalise(raw, table)
            if missing:
                st.error(f"{table}: missing required column(s): {', '.join(missing)}")
            else:
                ready[table] = df
                st.write(f"**{table}** - {len(df)} rows")
                st.dataframe(df.head(5), hide_index=True)
        if ready and st.button("Import and replace these tables", type="primary", key="do_import"):
            for table, df in ready.items():
                db.write_table(table, _clean(df))
            db.prune_allocations()
            _bump("import")
            st.toast("Import complete.")
            st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Reset to demo data**")
        if st.button("Load demo data", key="load_demo"):
            load_sample_into_db()
            st.toast("Demo data loaded.")
            st.rerun()
    with c2:
        st.markdown("**Delete everything**")
        sure = st.checkbox("I understand this deletes all faculty, courses and allocations", key="sure_wipe")
        if st.button("Delete all data", disabled=not sure, key="wipe"):
            db.clear_all()
            st.toast("All data deleted.")
            st.rerun()


# ---------------------------------------------------------------------- page
def render():
    st.header("Data Management")
    ctx = load_all()
    issues = validate_inputs(ctx.faculty, ctx.courses, ctx.prefs, ctx.past, ctx.settings)
    errs = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warning"]
    label = ("Data validation: all good" if not issues else
             f"Data validation: {len(errs)} error(s), {len(warns)} warning(s)")
    with st.expander(label, expanded=has_errors(issues)):
        if not issues:
            st.success("No problems found.")
        for i in errs:
            st.error(i["message"])
        for i in warns:
            st.warning(i["message"])

    fids = list(ctx.faculty["fid"].dropna().astype(str))
    codes = list(ctx.courses["code"].dropna().astype(str))
    tabs = st.tabs(["Faculty", "Courses", "Preferences", "Past teaching", "Workload rules",
                    "Import / Reset"])

    with tabs[0]:
        _editor("faculty", "faculty", {
            "fid": st.column_config.TextColumn("ID", required=True),
            "name": st.column_config.TextColumn("Name", required=True),
            "designation": st.column_config.SelectboxColumn("Designation", options=DESIGNATIONS),
            "min_hours": st.column_config.NumberColumn("Min hrs/week", min_value=0, step=1),
            "max_hours": st.column_config.NumberColumn("Max hrs/week", min_value=0, step=1),
            "expertise": st.column_config.TextColumn("Expertise tags", help="Separate with ;  e.g. ai;databases"),
            "unavailable_slots": st.column_config.TextColumn(
                "Unavailable slots", help="Blocked day-period slots, e.g. Mon-1;Tue-3. Empty = free all week."),
        }, _save_faculty,
            "Leave min/max blank to use the designation defaults. Slots look like Mon-1 (day-period).")

    with tabs[1]:
        _editor("courses", "courses", {
            "code": st.column_config.TextColumn("Code", required=True),
            "name": st.column_config.TextColumn("Name", required=True),
            "credits": st.column_config.NumberColumn("Credits", min_value=0, step=1),
            "weekly_hours": st.column_config.NumberColumn("Weekly hours", min_value=0, step=1, required=True),
            "type": st.column_config.SelectboxColumn("Type", options=COURSE_TYPES, required=True),
            "required_skill": st.column_config.TextColumn("Required skill(s)", help="Separate with ;"),
            "slots": st.column_config.TextColumn("Timetable slots", help="e.g. Mon-1;Wed-1;Fri-1"),
        }, _save_courses,
            "Timetable slots are used to detect clashes. List one slot per weekly hour.")

    with tabs[2]:
        _editor("preferences", "preferences", {
            "fid": st.column_config.SelectboxColumn("Faculty", options=fids, required=True),
            "code": st.column_config.SelectboxColumn("Course", options=codes, required=True),
            "rank": st.column_config.NumberColumn("Rank (1 = most wanted)", min_value=1, max_value=10, step=1, required=True),
        }, lambda e: _save_simple(e, ["fid", "code"]),
            "Soft constraint: faculty preferences raise the suitability score.")

    with tabs[3]:
        _editor("past_teaching", "past teaching", {
            "fid": st.column_config.SelectboxColumn("Faculty", options=fids, required=True),
            "code": st.column_config.TextColumn("Course code taught before", required=True),
        }, lambda e: _save_simple(e, ["fid", "code"]),
            "Soft constraint: continuity with previously taught courses raises the suitability score.")

    with tabs[4]:
        s = ctx.settings
        st.caption("Load(f) = sum of (weekly hours x type weight) over the courses assigned to f.")
        with st.form("rules"):
            c1, c2, c3 = st.columns(3)
            wt = c1.number_input("Theory weight", 0.0, 5.0, float(s["w_theory"]), 0.1)
            wl = c2.number_input("Lab weight", 0.0, 5.0, float(s["w_lab"]), 0.1)
            wu = c3.number_input("Tutorial weight", 0.0, 5.0, float(s["w_tutorial"]), 0.1)
            st.markdown("Suitability = weighted mix of these three (weights are normalised):")
            c1, c2, c3 = st.columns(3)
            we = c1.number_input("Expertise match", 0.0, 1.0, float(s["w_expertise"]), 0.05)
            wp = c2.number_input("Past teaching", 0.0, 1.0, float(s["w_past"]), 0.05)
            wf = c3.number_input("Stated preference", 0.0, 1.0, float(s["w_pref"]), 0.05)
            st.markdown("Dashboard alerts and baseline:")
            c1, c2, c3 = st.columns(3)
            ov = c1.number_input("Overloaded above average by (%)", 1, 100, int(s["overload_pct"]))
            un = c2.number_input("Underloaded below average by (%)", 1, 100, int(s["underload_pct"]))
            bm = c3.number_input("Manual allocation takes (minutes)", 1, 10000, int(s["manual_baseline_minutes"]))
            if st.form_submit_button("Save rules", type="primary"):
                db.save_settings({"w_theory": wt, "w_lab": wl, "w_tutorial": wu, "w_expertise": we,
                                  "w_past": wp, "w_pref": wf, "overload_pct": ov, "underload_pct": un,
                                  "manual_baseline_minutes": bm})
                st.toast("Rules saved. Regenerate the allocation to apply them.")
                st.rerun()
        if st.button("Restore default rules", key="reset_rules"):
            db.save_settings(DEFAULT_SETTINGS)
            st.rerun()

    with tabs[5]:
        _import_tab()
