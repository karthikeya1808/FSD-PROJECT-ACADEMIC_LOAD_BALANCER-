"""Academic Load Balancer for Faculty - Streamlit entry point."""
import hmac
import os

import streamlit as st

st.set_page_config(page_title="Academic Load Balancer", page_icon="⚖️", layout="wide")

# Streamlit Cloud keeps secrets in st.secrets; expose the ones we use as env vars.
try:
    for _k in ("DATABASE_URL", "ADMIN_PASSWORD"):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # no secrets file: perfectly fine
    pass

from core import db  # noqa: E402  (after secrets -> env)
from views import allocate, dashboard, data_management, export_page, override  # noqa: E402
from views.common import load_all  # noqa: E402

PAGES = {
    "Data Management": data_management.render,
    "Allocate": allocate.render,
    "Dashboard": dashboard.render,
    "Manual Override": override.render,
    "Export Reports": export_page.render,
}


@st.cache_resource
def _init_db():
    db.init_db()
    return True


def _login_gate():
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not password or st.session_state.get("auth"):
        return
    st.title("⚖️ Academic Load Balancer")
    entered = st.text_input("Administrator password", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), password.encode()):
            st.session_state["auth"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


_login_gate()
_init_db()

with st.sidebar:
    st.title("⚖️ Academic Load Balancer")
    st.caption("Fair, constraint-driven course allocation for faculty")
    page = st.radio("Navigate", list(PAGES), key="page", label_visibility="collapsed")
    ctx = load_all()
    st.divider()
    st.caption(f"**{len(ctx.fac)}** faculty · **{len(ctx.crs)}** courses · "
               f"allocation: **{'ready' if ctx.assign else 'not generated'}**")
    st.caption(f"Database: {db.backend_name()}")
    if db.backend_name().startswith("SQLite"):
        st.caption("Local SQLite resets when free hosting restarts the app. "
                   "Set a DATABASE_URL secret (free Neon Postgres) to keep data.")

PAGES[page]()
