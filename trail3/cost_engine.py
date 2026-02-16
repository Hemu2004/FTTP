
# from config import *

# class CostBreakdown:
#     def __init__(self, trench, fibre, labour, equipment, overhead, contingency, total):
#         self.trench = trench
#         self.fibre = fibre
#         self.labour = labour
#         self.equipment = equipment
#         self.overhead = overhead
#         self.contingency = contingency
#         self.total = total

# def calculate_base_cost(distance, premises):
#     trench = distance * TRENCH_RATE
#     fibre = distance * FIBRE_RATE
#     labour = premises * LABOUR_RATE
#     equipment = premises * EQUIPMENT_RATE

#     subtotal = trench + fibre + labour + equipment
#     overhead = subtotal * OVERHEAD_PERCENT
#     contingency = subtotal * CONTINGENCY_PERCENT
#     total = subtotal + overhead + contingency

#     return CostBreakdown(trench, fibre, labour, equipment, overhead, contingency, total)

def compute_cost(state):
    """Compute base cost using the centralized cost catalog.

    This replaces hard-coded unit rates (previously embedded in code) so costs are
    consistent, versioned, and auditable.
    """

    from cost_catalog import load_catalog, get_unit_cost, get_uplift

    catalog = load_catalog()

    fibre_material_per_m = get_unit_cost(catalog, "fibre_material_per_m", 8.0)
    trench_civil_per_m = get_unit_cost(catalog, "trench_civils_per_m", 25.0)
    labour_rate_per_day = get_unit_cost(catalog, "labour_rate_per_day", float(state.get("labour_rate", 500.0)))
    equipment_per_premise = get_unit_cost(catalog, "equipment_per_premise", 2000.0)

    # Simple productivity model (can be upgraded later)
    labour_productivity_m_per_day = 50.0

    # Uplifts
    location_key = (state.get("build_type") or "").lower().replace("_", "-")
    terrain_key = (state.get("terrain") or "").lower()
    traffic_key = (state.get("traffic") or "").lower()
    uplift_location = get_uplift(catalog, "location_type", location_key, 1.0)
    uplift_terrain = get_uplift(catalog, "terrain_type", terrain_key, 1.0)
    uplift_traffic = get_uplift(catalog, "traffic_management", traffic_key, 1.0)
    uplift = uplift_location * uplift_terrain * uplift_traffic

    # Apply build method nuance (lightweight): underground has higher civils; overhead lower.
    build_method = (state.get("build_method") or "").lower()
    if build_method == "underground":
        trench_multiplier = 1.15
    elif build_method == "overhead":
        trench_multiplier = 0.65
    else:
        trench_multiplier = 1.00

    fibre_cost = state["fibre_distance_m"] * fibre_material_per_m * uplift
    trench_cost = state["trench_length_m"] * trench_civil_per_m * trench_multiplier * uplift

    labour_days = state["trench_length_m"] / labour_productivity_m_per_day
    labour_cost = labour_days * labour_rate_per_day * uplift

    equipment_cost = state["number_of_premises"] * equipment_per_premise

    base_cost = fibre_cost + trench_cost + labour_cost + equipment_cost

    cost_per_premise = (
        base_cost / state["number_of_premises"]
        if state["number_of_premises"] > 0 else 0
    )

    state["base_cost"] = base_cost
    state["catalog_version"] = catalog.get("version", "unknown")
    state["uplift_multiplier"] = uplift

    state.setdefault("expert_outputs", {})
    state["expert_outputs"].update({
        "fibre_material_cost": fibre_cost,
        "trench_civil_cost": trench_cost,
        "labour_days": labour_days,
        "labour_cost": labour_cost,
        "equipment_cost": equipment_cost,
        "cost_per_premise": cost_per_premise
    })

    # Itemized breakdown for UI + audit packs
    state["cost_breakdown"] = {
        "Fibre materials": fibre_cost,
        "Civils / trenching": trench_cost,
        "Labour": labour_cost,
        "Equipment / CPE": equipment_cost,
    }

    return state
