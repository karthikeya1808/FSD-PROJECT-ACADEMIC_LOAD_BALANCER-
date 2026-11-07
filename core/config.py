"""Constants and default settings."""

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
COURSE_TYPES = ["theory", "lab", "tutorial"]
DESIGNATIONS = ["Professor", "Associate Professor", "Assistant Professor"]

# (min weekly hours, max weekly hours) used to pre-fill new faculty rows
DESIGNATION_HOURS = {
    "Professor": (4, 10),
    "Associate Professor": (6, 12),
    "Assistant Professor": (8, 14),
}

TABLES = {
    "faculty": ["fid", "name", "designation", "min_hours", "max_hours", "expertise", "unavailable_slots"],
    "courses": ["code", "name", "credits", "weekly_hours", "type", "required_skill", "slots"],
    "preferences": ["fid", "code", "rank"],
    "past_teaching": ["fid", "code"],
    "allocations": ["code", "fid", "suitability", "is_manual"],
}

NUMERIC_COLUMNS = {
    "faculty": ["min_hours", "max_hours"],
    "courses": ["credits", "weekly_hours"],
    "preferences": ["rank"],
    "allocations": ["suitability", "is_manual"],
}

DEFAULT_SETTINGS = {
    # workload weight per weekly hour, by course type
    "w_theory": 1.0,
    "w_lab": 1.5,
    "w_tutorial": 0.5,
    # suitability score weights (normalised to sum to 1 when used)
    "w_expertise": 0.6,
    "w_past": 0.2,
    "w_pref": 0.2,
    # solver
    "balance_weight": 10.0,      # penalty per 0.1 weighted hour of (max load - min load)
    "solver_seconds": 15,
    "rebalance_threshold": 1.0,  # heuristic re-balance runs while gap > this (weighted hours)
    # alerts / reporting
    "overload_pct": 20,
    "underload_pct": 20,
    "manual_baseline_minutes": 240,
}
