"""Demo data: a 10-member CS department with 34 courses (all fictional)."""
from pathlib import Path

import pandas as pd

from .config import TABLES

MWF = ["Mon", "Wed", "Fri"]
TTF = ["Tue", "Thu", "Fri"]


def _slots(days, period):
    return ";".join(f"{d}-{period}" for d in days)


def sample_frames() -> dict:
    faculty = [
        ("F01", "Dr. Anita Sharma", "Professor", 4, 10, "ai;machine learning;data science", "Fri-5;Fri-6"),
        ("F02", "Dr. Rajesh Kumar", "Professor", 4, 10, "networks;security;operating systems", "Mon-1;Wed-1;Fri-1"),
        ("F03", "Dr. Meera Iyer", "Associate Professor", 6, 12, "databases;data science;cloud", "Tue-6;Thu-6"),
        ("F04", "Dr. Sanjay Gupta", "Associate Professor", 6, 12, "algorithms;theory;mathematics", "Mon-5;Mon-6;Wed-5;Wed-6"),
        ("F05", "Dr. Priya Nair", "Associate Professor", 6, 12, "software engineering;web development;cloud", "Tue-1;Thu-1"),
        ("F06", "Mr. Arjun Singh", "Assistant Professor", 8, 14, "web development;programming;databases", "Fri-3;Fri-4"),
        ("F07", "Ms. Kavita Rao", "Assistant Professor", 8, 14, "ai;machine learning;programming", "Mon-2;Wed-2"),
        ("F08", "Mr. Vikram Joshi", "Assistant Professor", 8, 14, "operating systems;computer architecture;programming", "Thu-1;Thu-2;Thu-3"),
        ("F09", "Ms. Neha Verma", "Assistant Professor", 8, 14, "networks;cloud;security", "Wed-3;Wed-4"),
        ("F10", "Dr. Harpreet Kaur", "Assistant Professor", 8, 14, "mathematics;algorithms;data science", "Tue-5;Tue-6"),
    ]

    theory = [  # code, name, credits, hours, skill, days, period
        ("CS101", "Programming Fundamentals", 3, 3, "programming", MWF, 1),
        ("CS102", "Discrete Mathematics", 3, 3, "mathematics", TTF, 1),
        ("CS201", "Data Structures", 4, 4, "algorithms", ["Mon", "Tue", "Thu", "Fri"], 2),
        ("CS202", "Database Management Systems", 3, 3, "databases", MWF, 3),
        ("CS203", "Operating Systems", 3, 3, "operating systems", TTF, 2),
        ("CS204", "Computer Organization", 3, 3, "computer architecture", MWF, 2),
        ("CS205", "Theory of Computation", 3, 3, "theory", TTF, 3),
        ("CS301", "Machine Learning", 3, 3, "machine learning", MWF, 4),
        ("CS302", "Computer Networks", 3, 3, "networks", TTF, 4),
        ("CS303", "Software Engineering", 3, 3, "software engineering", MWF, 5),
        ("CS304", "Design and Analysis of Algorithms", 3, 3, "algorithms", TTF, 5),
        ("CS305", "Web Technologies", 3, 3, "web development", MWF, 6),
        ("CS306", "Cloud Computing", 3, 3, "cloud", TTF, 6),
        ("CS401", "Artificial Intelligence", 3, 3, "ai", MWF, 4),
        ("CS402", "Information Security", 3, 3, "security", TTF, 4),
        ("CS403", "Data Science and Analytics", 3, 3, "data science", MWF, 3),
        ("CS404", "Big Data Systems", 3, 3, "data science;cloud", TTF, 3),
        ("CS405", "Probability and Statistics", 3, 3, "mathematics", MWF, 1),
    ]
    labs = [  # code, name, credits, hours, skill, slots
        ("CS151", "Programming Lab", 1, 2, "programming", "Mon-3;Mon-4"),
        ("CS251", "Data Structures Lab", 1, 2, "algorithms", "Tue-3;Tue-4"),
        ("CS252", "DBMS Lab", 1, 2, "databases", "Wed-3;Wed-4"),
        ("CS253", "Operating Systems Lab", 1, 2, "operating systems", "Thu-3;Thu-4"),
        ("CS351", "Machine Learning Lab", 1, 2, "machine learning", "Fri-3;Fri-4"),
        ("CS352", "Networks Lab", 1, 2, "networks", "Mon-5;Mon-6"),
        ("CS353", "Web Technologies Lab", 2, 3, "web development", "Tue-4;Tue-5;Tue-6"),
        ("CS451", "Cloud Computing Lab", 1, 2, "cloud", "Wed-5;Wed-6"),
        ("CS452", "Security Lab", 1, 2, "security", "Thu-5;Thu-6"),
    ]
    tutorials = [  # code, name, skill, slot
        ("TU101", "Mathematics Tutorial", "mathematics", "Mon-6"),
        ("TU201", "Data Structures Tutorial", "algorithms", "Tue-6"),
        ("TU202", "DBMS Tutorial", "databases", "Wed-6"),
        ("TU301", "Machine Learning Tutorial", "machine learning", "Thu-6"),
        ("TU302", "Networks Tutorial", "networks", "Fri-6"),
        ("TU303", "Software Engineering Tutorial", "software engineering", "Mon-5"),
        ("TU401", "AI Tutorial", "ai", "Tue-5"),
    ]
    courses = (
        [(c, n, cr, h, "theory", sk, _slots(d, p)) for c, n, cr, h, sk, d, p in theory]
        + [(c, n, cr, h, "lab", sk, sl) for c, n, cr, h, sk, sl in labs]
        + [(c, n, 0, 1, "tutorial", sk, sl) for c, n, sk, sl in tutorials]
    )

    prefs = {
        "F01": ["CS401", "CS301", "CS403"], "F02": ["CS302", "CS402", "CS203"],
        "F03": ["CS202", "CS403", "CS404"], "F04": ["CS304", "CS205", "CS102"],
        "F05": ["CS303", "CS305", "TU303"], "F06": ["CS305", "CS353", "CS252"],
        "F07": ["CS301", "CS351", "CS101"], "F08": ["CS203", "CS204", "CS253"],
        "F09": ["CS306", "CS352", "CS451"], "F10": ["CS405", "CS201", "CS102"],
    }
    past = {
        "F01": ["CS301", "CS401"], "F02": ["CS302", "CS402", "CS352"],
        "F03": ["CS202", "CS252", "CS403"], "F04": ["CS201", "CS304"],
        "F05": ["CS303", "CS305"], "F06": ["CS101", "CS305", "CS353"],
        "F07": ["CS401", "CS351"], "F08": ["CS203", "CS253", "CS204"],
        "F09": ["CS306", "CS451", "CS352"], "F10": ["CS405", "CS102", "TU101"],
    }
    return {
        "faculty": pd.DataFrame(faculty, columns=TABLES["faculty"]),
        "courses": pd.DataFrame(courses, columns=TABLES["courses"]),
        "preferences": pd.DataFrame(
            [(f, c, i + 1) for f, cs in prefs.items() for i, c in enumerate(cs)],
            columns=TABLES["preferences"]),
        "past_teaching": pd.DataFrame(
            [(f, c) for f, cs in past.items() for c in cs], columns=TABLES["past_teaching"]),
    }


def load_sample_into_db() -> None:
    from . import db

    frames = sample_frames()
    for name, df in frames.items():
        db.write_table(name, df)
    db.write_table("allocations", pd.DataFrame(columns=TABLES["allocations"]))


def write_sample_files(folder) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, df in sample_frames().items():
        df.to_csv(folder / f"{name}.csv", index=False)
