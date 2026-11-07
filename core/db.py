"""Persistence layer.

SQLite is used by default (zero set-up).  Set the DATABASE_URL environment
variable (or Streamlit secret) to a PostgreSQL URL - e.g. a free Neon or
Supabase database - to make data survive restarts on free hosting.
"""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect

from .config import DEFAULT_SETTINGS, NUMERIC_COLUMNS, TABLES

_ENGINE = None
_ENGINE_URL = None


def _default_url() -> str:
    base = Path(__file__).resolve().parent.parent / "data"
    try:
        base.mkdir(exist_ok=True)
        probe = base / ".write_test"
        probe.touch()
        probe.unlink()
    except OSError:
        base = Path(tempfile.gettempdir())
    return f"sqlite:///{base / 'academic_load_balancer.db'}"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip() or _default_url()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def backend_name() -> str:
    return "SQLite (local file)" if database_url().startswith("sqlite") else "PostgreSQL"


def get_engine():
    global _ENGINE, _ENGINE_URL
    url = database_url()
    if _ENGINE is None or _ENGINE_URL != url:
        _ENGINE = create_engine(url, pool_pre_ping=True, pool_recycle=300)
        _ENGINE_URL = url
    return _ENGINE


# --------------------------------------------------------------------- tables
def _empty(name: str) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in TABLES[name]})


def read_table(name: str) -> pd.DataFrame:
    eng = get_engine()
    if not inspect(eng).has_table(name):
        return _empty(name)
    df = pd.read_sql_table(name, eng)
    for c in TABLES[name]:
        if c not in df.columns:
            df[c] = None
    df = df[TABLES[name]].copy()
    for c in NUMERIC_COLUMNS.get(name, []):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def write_table(name: str, df: pd.DataFrame) -> None:
    df = df.copy()
    for c in TABLES[name]:
        if c not in df.columns:
            df[c] = None
    df = df[TABLES[name]]
    df.to_sql(name, get_engine(), if_exists="replace", index=False)


# ------------------------------------------------------------------- settings
def _read_kv() -> dict:
    eng = get_engine()
    if not inspect(eng).has_table("settings"):
        return {}
    df = pd.read_sql_table("settings", eng)
    return dict(zip(df["k"].astype(str), df["v"].astype(str)))


def _write_kv(kv: dict) -> None:
    df = pd.DataFrame({"k": list(kv.keys()), "v": [str(v) for v in kv.values()]})
    df.to_sql("settings", get_engine(), if_exists="replace", index=False)


def get_settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    kv = _read_kv()
    for k in DEFAULT_SETTINGS:
        if k in kv:
            try:
                out[k] = float(kv[k])
            except ValueError:
                pass
    return out


def save_settings(values: dict) -> None:
    kv = _read_kv()
    for k, v in values.items():
        if k in DEFAULT_SETTINGS:
            kv[k] = v
    _write_kv(kv)


def get_last_run():
    raw = _read_kv().get("last_run")
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def save_last_run(info: dict) -> None:
    kv = _read_kv()
    kv["last_run"] = json.dumps(info)
    _write_kv(kv)


# ---------------------------------------------------------------- allocations
def get_assignment():
    """Return ({course_code: faculty_id}, {manually_overridden_course_codes})."""
    df = read_table("allocations")
    assign, manual = {}, set()
    for r in df.to_dict("records"):
        code, fid = str(r["code"]), str(r["fid"])
        assign[code] = fid
        if r.get("is_manual") == 1:
            manual.add(code)
    return assign, manual


def save_assignment(assign: dict, manual: set, suit: dict) -> None:
    rows = []
    for code, fid in assign.items():
        s = suit.get((fid, code), {}).get("score", 0.0)
        rows.append({"code": code, "fid": fid, "suitability": round(float(s), 1),
                     "is_manual": 1 if code in manual else 0})
    write_table("allocations", pd.DataFrame(rows, columns=TABLES["allocations"]))


def prune_allocations() -> None:
    """Drop allocation rows that point to faculty/courses that no longer exist."""
    alloc = read_table("allocations")
    if alloc.empty:
        return
    fids = set(read_table("faculty")["fid"].astype(str))
    codes = set(read_table("courses")["code"].astype(str))
    keep = alloc[alloc["fid"].astype(str).isin(fids) & alloc["code"].astype(str).isin(codes)]
    if len(keep) != len(alloc):
        write_table("allocations", keep)


# ------------------------------------------------------------------ lifecycle
def clear_all() -> None:
    for name in TABLES:
        write_table(name, _empty(name))
    _write_kv({})


def init_db() -> None:
    """Create tables on first run and fill them with demo data."""
    eng = get_engine()
    if inspect(eng).has_table("faculty"):
        return
    from .sample_data import load_sample_into_db  # local import avoids a cycle

    load_sample_into_db()
    save_last_run_marker()


def save_last_run_marker() -> None:
    kv = _read_kv()
    kv.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    _write_kv(kv)
