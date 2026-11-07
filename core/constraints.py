"""Hard-constraint checking, shared by the solver result check and manual override."""
from .utils import fmt_slots

GROUP_LABELS = {
    "availability": "faculty availability (blocked slots)",
    "clash": "timetable clashes",
    "hours_max": "maximum weekly hours per designation",
    "hours_min": "minimum weekly hours per designation",
}


def _v(kind, fid, code, message):
    return {"type": kind, "faculty": fid, "course": code, "message": message}


def check_allocation(assign: dict, fac: dict, crs: dict, relax=()):
    """Return a list of hard-constraint violations (empty list = fully valid)."""
    out = []
    by_fac = {f: [] for f in fac}
    for code, c in crs.items():
        f = assign.get(code)
        if f is None or f not in fac:
            out.append(_v("unassigned", "", code,
                          f"{code} ({c['name']}) is not assigned to any faculty member."))
        else:
            by_fac[f].append(code)

    for f, codes in by_fac.items():
        info = fac[f]
        name = info["name"]
        if "availability" not in relax:
            for code in codes:
                bad = crs[code]["slots"] & info["blocked"]
                if bad:
                    out.append(_v("availability", f, code,
                                  f"{name} is unavailable for {code} ({fmt_slots(bad)})."))
        if "clash" not in relax:
            seen = {}
            for code in codes:
                for s in crs[code]["slots"]:
                    seen.setdefault(s, []).append(code)
            for s, cs in sorted(seen.items()):
                if len(cs) > 1:
                    out.append(_v("clash", f, ", ".join(cs),
                                  f"Timetable clash for {name} at {s}: {', '.join(cs)}."))
        hours = sum(crs[c]["hours"] for c in codes)
        if "hours_max" not in relax and info["max"] is not None and hours > info["max"] + 1e-9:
            out.append(_v("hours_max", f, "",
                          f"{name} has {hours:g} h/week, above the maximum of {info['max']:g} h "
                          f"({info['designation'] or 'no designation'})."))
        if "hours_min" not in relax and info["min"] is not None and hours < info["min"] - 1e-9:
            out.append(_v("hours_min", f, "",
                          f"{name} has {hours:g} h/week, below the minimum of {info['min']:g} h "
                          f"({info['designation'] or 'no designation'})."))
    return out
