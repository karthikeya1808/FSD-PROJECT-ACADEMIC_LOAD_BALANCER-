import copy
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")

from core.config import DEFAULT_SETTINGS  # noqa: E402
from core.constraints import check_allocation  # noqa: E402
from core.metrics import faculty_load_table, summary  # noqa: E402
from core.model import build_maps  # noqa: E402
from core.reports import excel_bytes, pdf_bytes, template_workbook  # noqa: E402
from core.sample_data import sample_frames  # noqa: E402
from core.scoring import build_suitability  # noqa: E402
from core.solver import allocate  # noqa: E402
from core.utils import invalid_slots, parse_slots  # noqa: E402
from core.validation import has_errors, validate_inputs  # noqa: E402
from views.common import violations_df  # noqa: E402

S = dict(DEFAULT_SETTINGS)


@pytest.fixture(scope="module")
def frames():
    return sample_frames()


@pytest.fixture(scope="module")
def result(frames):
    return allocate(frames["faculty"], frames["courses"], frames["preferences"],
                    frames["past_teaching"], S, time_limit=10)


def test_slot_parsing():
    assert parse_slots("mon-1; Tuesday 3,Wed:2") == {"Mon-1", "Tue-3", "Wed-2"}
    assert invalid_slots("Mon-1;Xyz-2;foo") == ["Xyz-2", "foo"]


def test_sample_data_validates(frames):
    issues = validate_inputs(frames["faculty"], frames["courses"], frames["preferences"],
                             frames["past_teaching"], S)
    assert not has_errors(issues), issues


def test_solver_zero_violations_every_course_once(frames, result):
    fac, crs = build_maps(frames["faculty"], frames["courses"], S)
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    a = result["assignment"]
    assert set(a) == set(crs)
    assert check_allocation(a, fac, crs) == []
    assert result["violations"] == []


def test_balance_and_expertise_quality(frames, result):
    fac, crs = build_maps(frames["faculty"], frames["courses"], S)
    suit = build_suitability(fac, crs, frames["preferences"], frames["past_teaching"], S)
    lt = faculty_load_table(result["assignment"], fac, crs, S)
    sm = summary(lt, result["assignment"], fac, crs, suit, [])
    assert sm["balance_score"] >= 75
    assert sm["expertise_match_rate"] >= 75
    assert (lt["status"] == "OK").all()


def test_higher_balance_weight_gives_fairer_loads(frames):
    gaps = {}
    for bw in (0.0, 20.0):
        s = dict(S, balance_weight=bw)
        r = allocate(frames["faculty"], frames["courses"], frames["preferences"],
                     frames["past_teaching"], s, time_limit=10)
        fac, crs = build_maps(frames["faculty"], frames["courses"], s)
        lt = faculty_load_table(r["assignment"], fac, crs, s)
        gaps[bw] = lt["load"].max() - lt["load"].min()
    assert gaps[20.0] < gaps[0.0]


def test_locked_override_is_respected(frames, result):
    code = "CS301"
    other = next(f for f in frames["faculty"]["fid"] if f != result["assignment"][code])
    r = allocate(frames["faculty"], frames["courses"], frames["preferences"],
                 frames["past_teaching"], S, locked={code: other}, relax=("availability",), time_limit=10)
    assert r["assignment"][code] == other


def test_override_check_detects_clash_and_availability(frames, result):
    fac, crs = build_maps(frames["faculty"], frames["courses"], S)
    trial = dict(result["assignment"])
    # F02 is blocked on Mon-1: CS101 meets Mon-1
    trial["CS101"] = "F02"
    kinds = {v["type"] for v in check_allocation(trial, fac, crs)}
    assert "availability" in kinds
    # two courses with the identical slot pattern for one person -> clash
    trial = dict(result["assignment"])
    trial["CS301"] = trial["CS401"] = "F01"   # both MWF period 4
    assert "clash" in {v["type"] for v in check_allocation(trial, fac, crs)}


def test_infeasible_is_diagnosed(frames):
    courses = copy.deepcopy(frames["courses"])
    # Every faculty member blocks Mon-1..: make a course nobody can attend
    faculty = copy.deepcopy(frames["faculty"])
    faculty["unavailable_slots"] = faculty["unavailable_slots"].fillna("") + ";Sat-1"
    courses.loc[courses["code"] == "CS101", "slots"] = "Sat-1;Sat-1;Sat-1"
    r = allocate(faculty, courses, frames["preferences"], frames["past_teaching"], S, time_limit=5)
    assert r["status"] == "INFEASIBLE"
    assert any("CS101" in line for line in r["diagnosis"])


def test_hours_capacity_conflict_is_diagnosed(frames):
    faculty = copy.deepcopy(frames["faculty"])
    faculty["max_hours"] = 4
    faculty["min_hours"] = 0
    r = allocate(faculty, frames["courses"], frames["preferences"], frames["past_teaching"], S, time_limit=5)
    assert r["status"] == "INFEASIBLE"
    assert any("exceed" in line for line in r["diagnosis"])


def test_reports_build(frames, result):
    fac, crs = build_maps(frames["faculty"], frames["courses"], S)
    suit = build_suitability(fac, crs, frames["preferences"], frames["past_teaching"], S)
    from core.metrics import allocation_table
    lt = faculty_load_table(result["assignment"], fac, crs, S)
    at = allocation_table(result["assignment"], fac, crs, suit)
    sm = summary(lt, result["assignment"], fac, crs, suit, [])
    vdf = violations_df([])
    assert excel_bytes(sm, lt, at, vdf)[:2] == b"PK"
    assert pdf_bytes(sm, lt, at, vdf)[:4] == b"%PDF"
    assert template_workbook()[:2] == b"PK"
