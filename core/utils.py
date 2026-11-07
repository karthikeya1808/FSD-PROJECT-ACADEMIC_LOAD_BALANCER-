"""Small parsing helpers shared by the engine and the UI."""
import re

import pandas as pd

from .config import DAYS


def is_blank(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return str(v).strip() == ""


def clean_str(v) -> str:
    return "" if is_blank(v) else str(v).strip()


def to_float(v, default=None):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if f != f else f  # NaN check


def split_items(v):
    return [p.strip() for p in re.split(r"[;,|\n]+", clean_str(v)) if p.strip()]


_SLOT_RE = re.compile(r"^([A-Za-z]{3,9})\s*[-_:/ ]\s*(\d{1,2})$")


def parse_slot(item: str):
    """'mon-1', 'Monday 1' -> 'Mon-1'.  Returns None when invalid."""
    m = _SLOT_RE.match(item.strip())
    if not m:
        return None
    day = m.group(1)[:3].title()
    if day not in DAYS:
        return None
    return f"{day}-{int(m.group(2))}"


def parse_slots(v) -> set:
    return {s for s in (parse_slot(i) for i in split_items(v)) if s}


def invalid_slots(v) -> list:
    return [i for i in split_items(v) if parse_slot(i) is None]


def slot_key(s: str):
    d, p = s.split("-")
    return (DAYS.index(d), int(p))


def fmt_slots(slots) -> str:
    return "; ".join(sorted(slots, key=slot_key))
