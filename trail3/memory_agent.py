
# import json
# import os

# MEMORY_FILE = "memory_store.json"

# def store_memory(state):
#     record = {
#         "distance": state["distance"],
#         "premises": state["premises"],
#         "cost_total": state["cost"].total,
#         "cost_trench": state["cost"].trench,
#         "cost_fibre": state["cost"].fibre,
#         "cost_labour": state["cost"].labour,
#         "cost_equipment": state["cost"].equipment,
#         "cost_overhead": state["cost"].overhead,
#         "cost_contingency": state["cost"].contingency,
#         "risk": state["risk"].score
#     }

#     if os.path.exists(MEMORY_FILE):
#         with open(MEMORY_FILE, "r") as f:
#             data = json.load(f)
#     else:
#         data = []

#     data.append(record)

#     with open(MEMORY_FILE, "w") as f:
#         json.dump(data, f, indent=4)

#     state["history"] = data
#     return state

# def load_memory():
#     if os.path.exists(MEMORY_FILE):
#         with open(MEMORY_FILE, "r") as f:
#             return json.load(f)
#     return []

# memory_agent.py

import json
import os
from datetime import datetime

MEMORY_FILE = "memory_store.json"
MAX_RECORDS = 100


def store_memory(state):

    # Calculate overhead and contingency if not present
    base_cost = state["base_cost"]
    overhead = base_cost * 0.10  # OVERHEAD_PERCENT from config
    contingency = base_cost * 0.08  # CONTINGENCY_PERCENT from config

    record = {
        "timestamp": datetime.now().isoformat(),
        "distance": state["distance"],
        "premises": state["premises"],
        "cost": state["final_cost"],  # Use final_cost as total
        "cost_trench": state["expert_outputs"]["trench_civil_cost"],
        "cost_fibre": state["expert_outputs"]["fibre_material_cost"],
        "cost_labour": state["expert_outputs"]["labour_cost"],
        "cost_overhead": overhead,
        "cost_contingency": contingency,
        "cost_equipment": state["expert_outputs"]["equipment_cost"],
        "risk": state["risk_multiplier"],  # Use multiplier as risk score
        "risk_level": "High" if state["risk_multiplier"] > 1.5 else "Medium" if state["risk_multiplier"] > 1.3 else "Low"
    }

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(record)

    # Rolling window pruning
    if len(data) > MAX_RECORDS:
        data = data[-MAX_RECORDS:]

    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

    state["history"] = data
    return state


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return []


def append_records(records):
    """Append one or more record dicts to the memory store file.

    Records may contain a `timestamp` as a datetime or ISO string; this
    helper normalizes timestamps to ISO format and enforces the rolling
    window defined by MAX_RECORDS.
    """
    if not isinstance(records, list):
        records = [records]

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    else:
        data = []

    for r in records:
        rec = dict(r)
        ts = rec.get("timestamp")
        if isinstance(ts, datetime):
            rec["timestamp"] = ts.isoformat()
        elif ts is None:
            rec["timestamp"] = datetime.now().isoformat()
        # ensure numeric fields are serializable (optional)
        data.append(rec)

    # Rolling window pruning
    if len(data) > MAX_RECORDS:
        data = data[-MAX_RECORDS:]

    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return data
