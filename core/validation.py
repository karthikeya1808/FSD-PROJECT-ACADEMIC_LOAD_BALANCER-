"""Input-data validation (workflow step 2)."""
from .config import COURSE_TYPES, DESIGNATIONS
from .model import build_maps
from .utils import clean_str, invalid_slots, is_blank, to_float


def _issue(level, msg):
    return {"level": level, "message": msg}


def validate_inputs(faculty, courses, prefs, past, settings):
    issues = []
    fids = [clean_str(v) for v in faculty["fid"] if not is_blank(v)]
    codes = [clean_str(v) for v in courses["code"] if not is_blank(v)]

    if not fids:
        issues.append(_issue("error", "No faculty defined."))
    if not codes:
        issues.append(_issue("error", "No courses defined."))
    for d in sorted({x for x in fids if fids.count(x) > 1}):
        issues.append(_issue("error", f"Duplicate faculty id: {d}"))
    for d in sorted({x for x in codes if codes.count(x) > 1}):
        issues.append(_issue("error", f"Duplicate course code: {d}"))

    for r in faculty.to_dict("records"):
        fid = clean_str(r["fid"])
        if not fid:
            continue
        mn, mx = to_float(r["min_hours"]), to_float(r["max_hours"])
        if mn is not None and mx is not None and mn > mx:
            issues.append(_issue("error", f"{fid}: minimum hours ({mn:g}) exceed maximum ({mx:g})."))
        if clean_str(r["designation"]) not in DESIGNATIONS:
            issues.append(_issue("warning", f"{fid}: designation '{clean_str(r['designation'])}' is not a standard one."))
        if is_blank(r["expertise"]):
            issues.append(_issue("warning", f"{fid}: no expertise tags, will score 0 on expertise match."))
        bad = invalid_slots(r["unavailable_slots"])
        if bad:
            issues.append(_issue("error", f"{fid}: invalid slot(s) {', '.join(bad)} (use e.g. Mon-1;Tue-3)."))

    for r in courses.to_dict("records"):
        code = clean_str(r["code"])
        if not code:
            continue
        if clean_str(r["type"]).lower() not in COURSE_TYPES:
            issues.append(_issue("error", f"{code}: type must be one of {', '.join(COURSE_TYPES)}."))
        hrs = to_float(r["weekly_hours"])
        if hrs is None or hrs <= 0:
            issues.append(_issue("error", f"{code}: weekly hours must be greater than 0."))
        bad = invalid_slots(r["slots"])
        if bad:
            issues.append(_issue("error", f"{code}: invalid slot(s) {', '.join(bad)} (use e.g. Mon-1;Wed-1)."))
        else:
            n = len({s for s in clean_str(r["slots"]).replace(",", ";").split(";") if s.strip()})
            if n == 0:
                issues.append(_issue("warning", f"{code}: no timetable slots, so clashes cannot be checked."))
            elif hrs and abs(n - hrs) > 1e-9:
                issues.append(_issue("warning", f"{code}: {n} slot(s) listed but weekly hours = {hrs:g}."))
        if is_blank(r["required_skill"]):
            issues.append(_issue("warning", f"{code}: no required skill, so every faculty member matches equally."))

    fid_set, code_set = set(fids), set(codes)
    for r in prefs.to_dict("records"):
        if clean_str(r["fid"]) not in fid_set or clean_str(r["code"]) not in code_set:
            issues.append(_issue("warning", f"Preference ({clean_str(r['fid'])}, {clean_str(r['code'])}) refers to an unknown faculty or course and is ignored."))
    for r in past.to_dict("records"):
        if clean_str(r["fid"]) not in fid_set:
            issues.append(_issue("warning", f"Past-teaching row for unknown faculty '{clean_str(r['fid'])}' is ignored."))

    if fids and codes and not any(i["level"] == "error" for i in issues):
        fac, crs = build_maps(faculty, courses, settings)
        total = sum(c["hours"] for c in crs.values())
        cap_max = sum(i["max"] for i in fac.values() if i["max"] is not None)
        cap_min = sum(i["min"] for i in fac.values() if i["min"] is not None)
        if total > cap_max:
            issues.append(_issue("error", f"Course hours ({total:g}) exceed total faculty capacity ({cap_max:g})."))
        if total < cap_min:
            issues.append(_issue("error", f"Course hours ({total:g}) are below total minimum hours ({cap_min:g})."))
        for code, c in crs.items():
            if not any(not (c["slots"] & i["blocked"]) for i in fac.values()):
                issues.append(_issue("error", f"{code}: no faculty member is available at its slots."))
            if c["skills"] and not any(c["skills"] & i["skills"] for i in fac.values()):
                issues.append(_issue("warning", f"{code}: nobody has the required skill '{'; '.join(sorted(c['skills']))}'."))
    return issues


def has_errors(issues) -> bool:
    return any(i["level"] == "error" for i in issues)
