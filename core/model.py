"""Turn raw DataFrames into the plain dictionaries the engine works with."""
from .utils import clean_str, parse_slots, split_items, to_float


def type_weight(course_type: str, settings: dict) -> float:
    return float(settings.get(f"w_{clean_str(course_type).lower()}", 1.0))


def build_maps(faculty_df, courses_df, settings):
    """Return (fac, crs) dictionaries keyed by faculty id / course code."""
    fac = {}
    for r in faculty_df.to_dict("records"):
        fid = clean_str(r.get("fid"))
        if not fid:
            continue
        fac[fid] = {
            "name": clean_str(r.get("name")) or fid,
            "designation": clean_str(r.get("designation")),
            "min": to_float(r.get("min_hours")),
            "max": to_float(r.get("max_hours")),
            "skills": {s.lower() for s in split_items(r.get("expertise"))},
            "blocked": parse_slots(r.get("unavailable_slots")),
        }
    crs = {}
    for r in courses_df.to_dict("records"):
        code = clean_str(r.get("code"))
        if not code:
            continue
        hours = to_float(r.get("weekly_hours"), 0.0)
        ctype = clean_str(r.get("type")).lower() or "theory"
        crs[code] = {
            "name": clean_str(r.get("name")) or code,
            "credits": to_float(r.get("credits"), 0.0),
            "hours": hours,
            "type": ctype,
            "skills": {s.lower() for s in split_items(r.get("required_skill"))},
            "slots": parse_slots(r.get("slots")),
            "load": hours * type_weight(ctype, settings),
        }
    return fac, crs
