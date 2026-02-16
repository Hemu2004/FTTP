
# from langgraph.graph import StateGraph
# from typing import TypedDict

# from cost_engine import calculate_base_cost
# from modifiers import calculate_factors, apply_factors
# from risk_engine import calculate_risk
# from simulation_engine import simulate_network
# from memory_agent import store_memory

# class AgentState(TypedDict):
#     distance: float
#     premises: int
#     build_type: str
#     terrain: str
#     contractor: str
#     traffic: str
#     priority: str
#     cost: object
#     risk: object
#     simulation: object
#     history: list

# def execution_node(state):
#     base = calculate_base_cost(state["distance"], state["premises"])
#     factors = calculate_factors(
#         state["build_type"],
#         state["terrain"],
#         state["contractor"],
#         state["traffic"],
#         state["priority"]
#     )
#     state["cost"] = apply_factors(base, factors)

#     state["risk"] = calculate_risk(
#         state["distance"],
#         state["terrain"],
#         state["build_type"],
#         state["traffic"],
#         state["priority"]
#     )

#     state["simulation"] = simulate_network(
#         state["distance"],
#         state["premises"]
#     )

#     return state

# builder = StateGraph(AgentState)
# builder.add_node("execute", execution_node)
# builder.add_node("memory", store_memory)

# builder.set_entry_point("execute")
# builder.add_edge("execute", "memory")

# graph = builder.compile()

# graph.py

from cost_engine import compute_cost
from risk_engine import compute_risk
from simulation_engine import simulate_network
from memory_agent import store_memory
from llm_engine import llm_validate
import uuid
from optimization_agent import heuristic_cost_optimizations


def execute_agent(state):

    # Ensure every run has a unique request id for traceability
    state.setdefault("request_id", str(uuid.uuid4()))

    retries = 0
    max_retries = 2

    while retries <= max_retries:

        # Map state keys for new functions
        state["fibre_distance_m"] = state["distance"]
        state["trench_length_m"] = state["distance"]
        state["number_of_premises"] = state["premises"]
        # Rates are loaded from cost_catalog.json inside compute_cost()
        state["location_type"] = state["build_type"].lower()
        state["terrain_type"] = state["terrain"].lower()

        # ------------------------------------
        # Build Method Decision (AI + guardrails)
        # ------------------------------------
        state.setdefault("assumptions", [])
        try:
            from llm_engine import run_build_method_agent
            decision = run_build_method_agent(state)
            state["build_method"] = decision.get("build_method", "Hybrid")
            state["survey_required"] = bool(decision.get("survey_required", False))
            state["build_method_confidence"] = float(decision.get("confidence", 0.5))
            for a in decision.get("assumptions", [])[:6]:
                if isinstance(a, str) and a.strip():
                    state["assumptions"].append(a.strip())
        except Exception:
            # Heuristic fallback
            if state["terrain"].lower() == "rocky" or state["build_type"].lower() == "rural":
                state["build_method"] = "Underground"
            else:
                state["build_method"] = "Hybrid"
            state["survey_required"] = state["terrain"].lower() in {"rocky", "water crossing"}
            state["build_method_confidence"] = 0.45
            state["assumptions"].append("Build method chosen by heuristic fallback.")

        # Compute cost
        state = compute_cost(state)
        # Deterministic optimization suggestions (stable, auditable)
        try:
            state["optimization_suggestions"] = heuristic_cost_optimizations(state)
        except Exception:
            state["optimization_suggestions"] = []
        # ------------------------------------
        # Cost Optimization Agent (AI)
        # ------------------------------------
        try:
            from llm_engine import run_cost_optimization_agent
            cost_insight = run_cost_optimization_agent(state)
            state["cost_validation"] = cost_insight.get("validation", "Checked")
            llm_opt = cost_insight.get("optimization", "None")
            # Merge deterministic + LLM suggestions into a single field for UI/report
            hints = state.get("optimization_suggestions") or []
            hint_text = "\n".join([
                f"- {h.get('title')}: {h.get('rationale')} (est. {h.get('estimated_savings_pct')}%)" for h in hints if isinstance(h, dict)
            ])
            if hint_text.strip():
                state["cost_optimization"] = f"Deterministic suggestions:\n{hint_text}\n\nLLM suggestion:\n- {llm_opt}"
            else:
                state["cost_optimization"] = llm_opt
        except Exception:
            state["cost_validation"] = "System Error"
            state["cost_optimization"] = "Manual Review Required"

        # Compute risk
        state = compute_risk(state)
        # ------------------------------------
        # Risk Agent (AI)
        # ------------------------------------
        try:
            from llm_engine import run_risk_agent
            risk_insight = run_risk_agent(state)
            state["top_risk"] = risk_insight.get("top_risk", "General Operational Risk")
            state["risk_mitigation"] = risk_insight.get("mitigation", "Standard Protocols")
        except Exception:
            state["top_risk"] = "Unknown"
            state["risk_mitigation"] = "Proceed with caution"

        # Simulation
        state["simulation"] = simulate_network(
            state["distance"],
            state["premises"]
        )

        # Final Aggregation
        state["final_cost"] = (
            state["base_cost"] * state.get("risk_multiplier", 1.0)
            + state.get("regulatory_cost", 0)
            + state.get("simulation_adjustment", 0)
        )

        state["confidence_score"] = 1 / state["risk_multiplier"]
        state["anomaly_flag"] = state["final_cost"] > 200000

        # LLM validation prompt
        prompt = f"""
        Validate this FTTP output.
        Return JSON ONLY:

        {{
            "status": "VALID or INVALID",
            "issue": "short explanation if invalid"
        }}

        Final Cost: {state["final_cost"]}
        Risk Multiplier: {state["risk_multiplier"]}
        Confidence Score: {state["confidence_score"]}
        Deployment Days: {state["simulation"].total_days}
        """

        try:
            # OpenAI validation only
            validation = llm_validate(prompt)
            if validation.get("status") == "VALID":
                state["validation"] = "VALID (OpenAI)"
                break
            else:
                retries += 1
                state["validation"] = f"Invalid: {validation.get('issue', 'N/A')}"
        except Exception as e:
            state["validation"] = f"LLM Error: {str(e)} - Assuming Valid"
            break

    # Conditional Branching
    if state["risk_multiplier"] > 1.5:
        state["mitigation"] = "Governance approval required due to high risk."
    else:
        # Generate AI Strategic Insight for normal/low risk scenarios
        try:
            from llm_engine import run_strategy_agent
            state["mitigation"] = run_strategy_agent(state)
        except Exception as e:
            state["mitigation"] = "Analysis complete. Proceed with standard deployment protocols."

    state = store_memory(state)

    return state





def scenario_estimates(base_state: dict) -> list:
    """Deterministic scenario comparison without LLM calls.
    Returns a list of scenario dicts with method, final_cost, risk_multiplier, confidence_score, total_days.
    """
    import copy as _copy
    scenarios = []
    for method in ["Underground", "Overhead", "Hybrid"]:
        s = _copy.deepcopy(base_state)
        s["build_method"] = method
        s.setdefault("assumptions", [])
        # Ensure mappings for compute_cost/compute_risk
        s["fibre_distance_m"] = s.get("distance", 0)
        s["trench_length_m"] = s.get("distance", 0)
        s["number_of_premises"] = s.get("premises", 0)
        s["location_type"] = str(s.get("build_type", "urban")).lower()
        s["terrain_type"] = str(s.get("terrain", "normal")).lower()
        try:
            s = compute_cost(s)
            s = compute_risk(s)
            s["simulation"] = simulate_network(s.get("distance", 0), s.get("premises", 0))
        except Exception:
            # keep partial if any error
            pass
        scenarios.append({
            "method": method,
            "final_cost": float(s.get("final_cost", s.get("total_cost", 0)) or 0),
            "risk_multiplier": float(s.get("risk_multiplier", 1.0) or 1.0),
            "confidence_score": float(s.get("confidence_score", 0.6) or 0.6),
            "total_days": int(getattr(s.get("simulation", None), "total_days", 0) or 0),
        })
    return scenarios
