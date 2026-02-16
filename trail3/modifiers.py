
# from cost_engine import CostBreakdown
# from config import OVERHEAD_PERCENT, CONTINGENCY_PERCENT

# def calculate_factors(build_type, terrain, contractor, traffic, priority):
#     factors = {
#         "civil": 1.0,
#         "fibre": 1.0,
#         "labour": 1.0,
#         "equipment": 1.0,
#         "priority_multiplier": 1.0
#     }

#     if terrain == "Rocky":
#         factors["civil"] *= 1.2
#     if terrain == "Water Crossing":
#         factors["civil"] *= 1.3
#     if build_type == "Urban":
#         factors["labour"] *= 1.15
#     if contractor == "Premium":
#         factors["civil"] *= 1.1
#         factors["fibre"] *= 1.1
#         factors["labour"] *= 1.1
#         factors["equipment"] *= 1.1
#     if traffic == "Yes":
#         factors["civil"] *= 1.08
#     if priority == "Urgent":
#         factors["priority_multiplier"] *= 1.12

#     return factors

# def apply_factors(base, factors):
#     adjusted_trench = base.trench * factors["civil"]
#     adjusted_fibre = base.fibre * factors["fibre"]
#     adjusted_labour = base.labour * factors["labour"]
#     adjusted_equipment = base.equipment * factors["equipment"]

#     subtotal = adjusted_trench + adjusted_fibre + adjusted_labour + adjusted_equipment
#     overhead = subtotal * OVERHEAD_PERCENT
#     contingency = subtotal * CONTINGENCY_PERCENT
#     total = (subtotal + overhead + contingency) * factors["priority_multiplier"]

#     return CostBreakdown(adjusted_trench, adjusted_fibre, adjusted_labour, adjusted_equipment, overhead, contingency, total)
# modifiers.py

from cost_engine import CostBreakdown

def calculate_modifier(build_type, terrain, contractor, traffic, priority):

    modifier = 1.0

    if build_type == "Urban":
        modifier += 0.15
    elif build_type == "Rural":
        modifier -= 0.05

    if terrain == "Rocky":
        modifier += 0.20
    elif terrain == "Water Crossing":
        modifier += 0.30

    if contractor == "Premium":
        modifier += 0.10

    if traffic == "Yes":
        modifier += 0.08

    if priority == "Urgent":
        modifier += 0.12

    return modifier


def apply_modifier(base: CostBreakdown, modifier: float):

    return CostBreakdown(
        trench=base.trench * modifier,
        fibre=base.fibre * modifier,
        labour=base.labour * modifier,
        equipment=base.equipment * modifier,
        overhead=base.overhead * modifier,
        contingency=base.contingency * modifier,
        total=base.total * modifier
    )
