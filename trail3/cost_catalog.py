import json
import os
from typing import Any, Dict

CATALOG_FILE = os.getenv("COST_CATALOG_FILE", "cost_catalog.json")


def load_catalog() -> Dict[str, Any]:
    if not os.path.exists(CATALOG_FILE):
        raise FileNotFoundError(f"Cost catalog not found: {CATALOG_FILE}")
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_catalog(catalog: Dict[str, Any]) -> None:
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)


def get_unit_cost(catalog: Dict[str, Any], key: str, default: float) -> float:
    return float(catalog.get("unit_costs", {}).get(key, default))


def get_uplift(catalog: Dict[str, Any], category: str, key: str, default: float = 1.0) -> float:
    return float(catalog.get("uplifts", {}).get(category, {}).get(key, default))
