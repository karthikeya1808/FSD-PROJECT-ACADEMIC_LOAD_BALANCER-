"""Smoke test: drive the real Streamlit app through every page."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "app.db")
os.environ.pop("ADMIN_PASSWORD", None)

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def _go(at, page):
    at.sidebar.radio(key="page").set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_full_flow():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]

    _go(at, "Data Management")
    _go(at, "Dashboard")
    assert any("No allocation" in i.value for i in at.info)

    _go(at, "Allocate")
    at.button(key="btn_generate").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("allocation found" in s.value.lower() for s in at.success), [s.value for s in at.success]

    _go(at, "Dashboard")
    assert len(at.metric) >= 6
    assert any("No overloaded" in s.value for s in at.success)

    _go(at, "Manual Override")
    at.selectbox(key="ov_course").set_value("CS301").run()
    cur = at.selectbox(key="ov_new_CS301").value
    options = at.selectbox(key="ov_new_CS301").options
    other = next(o for o in options if "[current]" not in o)
    at.selectbox(key="ov_new_CS301").set_value(other).run()
    assert not at.exception, [e.value for e in at.exception]
    at.button(key="ov_apply").click().run()
    assert not at.exception, [e.value for e in at.exception]

    _go(at, "Dashboard")
    assert any("manually overridden" in c.value for c in at.caption)

    _go(at, "Export Reports")
    assert not at.exception
