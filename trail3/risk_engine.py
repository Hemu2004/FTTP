
# class RiskResult:
#     def __init__(self, score, level):
#         self.score = score
#         self.level = level

# def calculate_risk(distance, terrain, build_type, traffic, priority):
#     score = 0

#     if distance > 800:
#         score += 25
#     if terrain == "Rocky":
#         score += 30
#     if terrain == "Water Crossing":
#         score += 40
#     if build_type == "Urban":
#         score += 20
#     if traffic == "Yes":
#         score += 15
#     if priority == "Urgent":
#         score += 10

#     if score >= 60:
#         level = "High"
#     elif score >= 30:
#         level = "Medium"
#     else:
#         level = "Low"

#     return RiskResult(score, level)

def compute_risk(state):

    multiplier = 1.0

    if state["location_type"] == "urban":
        multiplier += 0.3

    if state["terrain_type"] == "rocky":
        multiplier += 0.25

    state["risk_multiplier"] = multiplier

    state.setdefault("expert_outputs", {})
    state["expert_outputs"]["risk_multiplier"] = multiplier

    return state
