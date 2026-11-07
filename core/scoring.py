"""Suitability scoring: expertise match + past teaching + stated preference."""
from .utils import clean_str, to_float

PREF_SCORES = {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4}   # rank 5+ -> 0.2, not listed -> 0


def pref_value(rank) -> float:
    r = to_float(rank)
    if r is None:
        return 0.0
    return PREF_SCORES.get(int(r), 0.2)


def norm_weights(settings: dict):
    w = (settings["w_expertise"], settings["w_past"], settings["w_pref"])
    total = sum(w)
    if total <= 0:
        return (1.0, 0.0, 0.0)
    return tuple(x / total for x in w)


def build_suitability(fac: dict, crs: dict, prefs_df, past_df, settings: dict) -> dict:
    """{(fid, code): {"score": 0-100, "expertise": 0-1, "past": 0/1, "pref": 0-1}}"""
    we, wp, wf = norm_weights(settings)
    pref_map = {
        (clean_str(r["fid"]), clean_str(r["code"])): pref_value(r.get("rank"))
        for r in prefs_df.to_dict("records")
    }
    past_set = {(clean_str(r["fid"]), clean_str(r["code"])) for r in past_df.to_dict("records")}
    out = {}
    for f, fi in fac.items():
        for c, ci in crs.items():
            req = ci["skills"]
            exp = 1.0 if not req else len(req & fi["skills"]) / len(req)
            past = 1.0 if (f, c) in past_set else 0.0
            pref = pref_map.get((f, c), 0.0)
            out[f, c] = {
                "score": 100.0 * (we * exp + wp * past + wf * pref),
                "expertise": exp,
                "past": past,
                "pref": pref,
            }
    return out
