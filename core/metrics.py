"""Load tables, alerts and evaluation metrics for a given assignment."""
import statistics

import pandas as pd

from .config import COURSE_TYPES


def faculty_load_table(assign, fac, crs, settings) -> pd.DataFrame:
    rows = []
    for f, info in fac.items():
        codes = [c for c, ff in assign.items() if ff == f and c in crs]
        row = {
            "fid": f, "name": info["name"], "designation": info["designation"],
            "courses": len(codes),
            "hours": sum(crs[c]["hours"] for c in codes),
            "load": round(sum(crs[c]["load"] for c in codes), 2),
            "min_hours": info["min"], "max_hours": info["max"],
        }
        for t in COURSE_TYPES:
            row[f"load_{t}"] = round(sum(crs[c]["load"] for c in codes if crs[c]["type"] == t), 2)
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    avg = df["load"].mean()
    over, under = settings["overload_pct"] / 100, settings["underload_pct"] / 100
    status = []
    for _, r in df.iterrows():
        if pd.notna(r["max_hours"]) and r["hours"] > r["max_hours"] + 1e-9:
            status.append("Over max hours")
        elif pd.notna(r["min_hours"]) and r["hours"] < r["min_hours"] - 1e-9:
            status.append("Under min hours")
        elif avg > 0 and r["load"] > avg * (1 + over):
            status.append("Overloaded")
        elif avg > 0 and r["load"] < avg * (1 - under):
            status.append("Underloaded")
        else:
            status.append("OK")
    df["status"] = status
    return df


def allocation_table(assign, fac, crs, suit) -> pd.DataFrame:
    rows = []
    for code, c in crs.items():
        f = assign.get(code)
        s = suit.get((f, code)) if f in fac else None
        rows.append({
            "code": code, "course": c["name"], "type": c["type"], "hours": c["hours"],
            "required_skill": "; ".join(sorted(c["skills"])),
            "faculty_id": f or "", "faculty": fac[f]["name"] if f in fac else "(unassigned)",
            "expertise_match": round(s["expertise"] * 100) if s else 0,
            "suitability": round(s["score"], 1) if s else 0.0,
        })
    return pd.DataFrame(rows)


def summary(loads_df, assign, fac, crs, suit, violations) -> dict:
    loads = list(loads_df["load"]) if not loads_df.empty else []
    out = {"assigned": sum(1 for c in crs if assign.get(c) in fac), "courses": len(crs)}
    if loads:
        mx, mn = max(loads), min(loads)
        out.update({
            "avg_load": round(statistics.fmean(loads), 2),
            "load_variance": round(statistics.pvariance(loads), 2),
            "load_std": round(statistics.pstdev(loads), 2),
            "max_load": mx, "min_load": mn, "balance_gap": round(mx - mn, 2),
            "balance_score": round(100 * (1 - (mx - mn) / mx), 1) if mx > 0 else 100.0,
        })
    req = [c for c in crs if crs[c]["skills"] and assign.get(c) in fac]
    out["expertise_match_rate"] = (round(100 * sum(1 for c in req
                                    if suit[assign[c], c]["expertise"] > 0) / len(req), 1)
                                   if req else None)
    with_pref = {f for (f, c), s in suit.items() if s["pref"] > 0}
    got = {assign[c] for c in crs if assign.get(c) in fac and suit[assign[c], c]["pref"] > 0}
    out["pref_satisfaction"] = round(100 * len(got) / len(with_pref), 1) if with_pref else None
    out["violations"] = len(violations)
    return out
