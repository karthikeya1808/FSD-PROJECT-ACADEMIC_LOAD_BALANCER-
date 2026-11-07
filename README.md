# Academic Load Balancer for Faculty

FSD project by **Tvisha Dogra (24BAI70734)** and **Karthikeya Sahukari (24BAI70795)**.

A web app that allocates theory, lab and tutorial courses to faculty **fairly and automatically**.
It matches expertise, respects availability and hour limits, balances workload, and reports the result
on a dashboard. The administrator can override any assignment and see constraint checks instantly.

Built with **Streamlit + OR-Tools CP-SAT + SQLAlchemy + Plotly + ReportLab/OpenPyXL**. Everything runs
in Python, so it deploys for free on Streamlit Community Cloud.

## Synopsis modules → code

| Synopsis module | Where |
|---|---|
| Data Management | `views/data_management.py`, `core/db.py`, `core/validation.py` |
| Allocation Engine (suitability scores, load, greedy start, re-balance) | `core/scoring.py`, `core/solver.py` (`greedy_initial`) |
| Constraint Solver (hard + soft, conflict report) | `core/solver.py` (`_run_cp`, `diagnose`), `core/constraints.py` |
| Manual Override (instant re-check) | `views/override.py` |
| Reporting Dashboard + PDF/Excel export | `views/dashboard.py`, `views/export_page.py`, `core/reports.py` |

### How the allocation works
* **Suitability** of faculty *f* for course *c* = weighted mix of expertise match, past teaching of that course and stated preference (0-100).
* **Load(f)** = Σ (weekly hours × type weight) over courses assigned to *f* (defaults: theory 1.0, lab 1.5, tutorial 0.5; editable).
* **Balance gap** = max load − min load.
* **Hard constraints:** each course has exactly one faculty member; no timetable clashes; blocked slots respected; min/max weekly hours per faculty (set from designation).
* **Objective:** maximise total suitability − `balance_weight` × balance gap.
* If no solution exists, the app tells you which constraints conflict (and which single group, if relaxed, makes it feasible).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501. The first launch loads demo data (10 faculty, 34 courses) into a local SQLite file.
Go to **Allocate → Generate Allocation**, then explore **Dashboard**, **Manual Override**, **Export Reports**.

Run the tests: `pip install pytest && pytest tests -q`

## Deploy for free (Streamlit Community Cloud + Neon)

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Academic Load Balancer"
git branch -M main
git remote add origin https://github.com/<your-username>/academic-load-balancer.git
git push -u origin main
```
(Create the empty repo on github.com first. A public repo is fine; no secrets are in the code.)

### 2. (Recommended) Free PostgreSQL on Neon so data survives restarts
1. Sign up at https://neon.tech and create a project.
2. Copy the **connection string** (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`).

Skipping this still works, but the SQLite file on free hosting is wiped whenever the app restarts or redeploys.

### 3. Deploy on Streamlit Community Cloud
1. Go to https://share.streamlit.io and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub**, pick your repo, branch `main`, main file `app.py`.
3. Open **Advanced settings**:
   * **Python version:** 3.11 or 3.12.
   * **Secrets:** paste
     ```toml
     DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
     ADMIN_PASSWORD = "choose-a-strong-password"
     ```
     `ADMIN_PASSWORD` is optional; if set, the app asks for it before showing anything.
4. Click **Deploy**. The first build takes a few minutes (OR-Tools is a big package). You get a URL like `https://your-app.streamlit.app`.

Streamlit Cloud puts free apps to sleep after inactivity; the first visit afterwards shows a "wake up" button.

### Alternative: Render (free web service)
New → Web Service → connect the repo. Build command `pip install -r requirements.txt`,
start command `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`,
add `DATABASE_URL` / `ADMIN_PASSWORD` as environment variables. Free instances sleep after ~15 min idle.

## Using your own data
**Data Management → Import / Reset** accepts one Excel workbook with sheets `faculty`, `courses`, `preferences`, `past_teaching`,
or separate CSVs with those names. Download the template there (or see `sample_data/`).

| Table | Columns |
|---|---|
| faculty | `fid, name, designation, min_hours, max_hours, expertise, unavailable_slots` |
| courses | `code, name, credits, weekly_hours, type (theory/lab/tutorial), required_skill, slots` |
| preferences | `fid, code, rank` (1 = most wanted) |
| past_teaching | `fid, code` |

* Lists use `;` as separator, e.g. expertise `ai;machine learning`.
* Slots are `Day-Period`, e.g. `Mon-1;Wed-1;Fri-1` (days Mon–Sat). Give one slot per weekly hour.
* `unavailable_slots` are the slots a faculty member **cannot** teach; empty means free all week.

## Demo script for the viva
1. Data Management: show faculty/courses, validation panel, workload rules.
2. Allocate: generate; mention solver status and runtime.
3. Dashboard: load chart, hours-vs-limits chart, balance score, expertise match, 0 violations.
4. Manual Override: move **CS301** to someone else, show the instant violation/impact preview, apply it.
5. Allocate again with "keep manual overrides" ticked: solver re-balances around your change.
6. Make it infeasible (e.g. set everyone's max hours to 4): show the conflict explanation.
7. Export PDF and Excel.

## Limitations (also in the synopsis)
Result quality depends on accurate data; teaching style and student feedback are not modelled; very large
departments may need a longer solver time limit (the heuristic result is used as a fallback).
# FSD-PROJECT-ACADEMIC_LOAD_BALANCER-
