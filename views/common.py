"""Helpers shared by all pages."""
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from core import db
from core.model import build_maps
from core.scoring import build_suitability


def load_all() -> SimpleNamespace:
    faculty = db.read_table("faculty")
    courses = db.read_table("courses")
    prefs = db.read_table("preferences")
    past = db.read_table("past_teaching")
    settings = db.get_settings()
    fac, crs = build_maps(faculty, courses, settings)
    suit = build_suitability(fac, crs, prefs, past, settings)
    assign, manual = db.get_assignment()
    assign = {c: f for c, f in assign.items() if c in crs and f in fac}
    return SimpleNamespace(faculty=faculty, courses=courses, prefs=prefs, past=past,
                           settings=settings, fac=fac, crs=crs, suit=suit,
                           assign=assign, manual=manual & set(assign),
                           last_run=db.get_last_run())


def goto(page: str) -> None:
    """Button callback: switch the sidebar page."""
    st.session_state["page"] = page


def violations_df(violations) -> pd.DataFrame:
    return pd.DataFrame(violations, columns=["type", "faculty", "course", "message"])
