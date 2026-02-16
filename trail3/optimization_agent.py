from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class OptimizationSuggestion:
    title: str
    rationale: str
    estimated_savings_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "rationale": self.rationale,
            "estimated_savings_pct": round(float(self.estimated_savings_pct), 1),
        }


def heuristic_cost_optimizations(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic optimizer.

    Goal: produce stable, explainable suggestions that never hallucinate numbers.
    These are used alongside the LLM optimization agent.
    """
    trench = float(state.get("trench_civil_cost", 0) or 0)
    labour = float(state.get("labour_cost", 0) or 0)
    fibre = float(state.get("fibre_material_cost", 0) or 0)
    base = float(state.get("base_cost", 0) or 0)
    build_method = (state.get("build_method") or "Hybrid").lower()
    traffic = (state.get("traffic") or "Standard").lower()
    terrain = (state.get("terrain") or "Normal").lower()
    location_type = (state.get("build_type") or state.get("location_type") or "Urban").lower()

    suggestions: List[OptimizationSuggestion] = []

    if base <= 0:
        return []

    trench_share = trench / base if base else 0
    labour_share = labour / base if base else 0

    if trench_share >= 0.45:
        suggestions.append(
            OptimizationSuggestion(
                title="Reduce civils via micro-trenching / HDD selection",
                rationale="Civils is the dominant cost driver. Consider micro-trenching in suitable corridors, or HDD for crossings to reduce open-cut length.",
                estimated_savings_pct=8.0,
            )
        )

    if labour_share >= 0.25:
        suggestions.append(
            OptimizationSuggestion(
                title="Optimize crew plan and work packaging",
                rationale="Labour share is elevated. Use clustered work orders, reduce travel/idle time, and schedule night work only where traffic management is critical.",
                estimated_savings_pct=4.0,
            )
        )

    if fibre / base >= 0.18 and build_method in {"overhead", "hybrid"}:
        suggestions.append(
            OptimizationSuggestion(
                title="Consider aerial sections where feasible",
                rationale="Material-heavy builds can benefit from aerial spans on existing pole routes where approvals allow.",
                estimated_savings_pct=3.5,
            )
        )

    # Contextual heuristics
    nearby = state.get("nearby_providers") or []
    if isinstance(nearby, list) and nearby:
        # If any provider is very close, suggest infra sharing as an option
        close = [p for p in nearby if isinstance(p, dict) and float(p.get("distance_km", 999)) <= 2.0]
        if close:
            names = ", ".join(sorted({str(p.get("name")) for p in close if p.get("name")}))
            suggestions.append(
                OptimizationSuggestion(
                    title="Evaluate infrastructure sharing",
                    rationale=f"Nearby operators detected ({names}). If commercial/regulated sharing is available, reuse ducts/ROW to reduce civils and accelerate delivery.",
                    estimated_savings_pct=6.0,
                )
            )

    if traffic in {"high", "critical"}:
        suggestions.append(
            OptimizationSuggestion(
                title="Minimize traffic management exposure",
                rationale="Traffic management drives both cost and schedule. Re-plan to off-peak windows and consolidate permits to reduce repeated setups.",
                estimated_savings_pct=2.5,
            )
        )

    if terrain in {"difficult", "extreme"} and location_type == "rural":
        suggestions.append(
            OptimizationSuggestion(
                title="Route selection to avoid hard terrain",
                rationale="In difficult rural terrain, small route changes can materially reduce civils complexity. Prioritize existing corridors and utility easements.",
                estimated_savings_pct=3.0,
            )
        )

    # Return top 3 to keep output concise
    suggestions = sorted(suggestions, key=lambda s: s.estimated_savings_pct, reverse=True)[:3]
    return [s.to_dict() for s in suggestions]
