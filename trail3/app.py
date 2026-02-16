import streamlit as st
import os
# Streamlit app - Optimized for reload
# Triggered reload 295
import json
import pandas as pd
import plotly.express as px
import pydeck as pdk
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from graph import execute_agent, scenario_estimates
from geo.geocoder import get_location_details
from report_generator import generate_costing_pack_pdf, generate_roi_report_pdf, generate_optimization_pack_pdf, generate_monthly_summary_pdf
from providers import find_nearby_providers, Provider

import folium
from streamlit_folium import st_folium

from audit_store import (
    save_request,
    update_status,
    get_request,
    list_recent,
    list_by_status,
    analytics_last_30_days,
    roi_observed_metrics,
    list_roi_snapshots,
    patch_output,
)

st.set_page_config(
    layout="wide",
    page_title="FTTP AI Command Center",
)

# -----------------------------
# UI theme / minimal enterprise styling
# -----------------------------
st.markdown(
    """
<style>
/* Simple enterprise palette (no neon) */
:root {
  --bg: #0f1115;
  --panel: #171a21;
  --card: #1d212b;
  --border: rgba(255,255,255,0.08);
  --text: rgba(255,255,255,0.92);
  --muted: rgba(255,255,255,0.65);
  --muted2: rgba(255,255,255,0.55);
  --gold: #b08a3b;
}

html, body, [class*="css"], .stApp {
  background: var(--bg) !important;
  color: var(--text) !important;
}

.block-container { padding-top: 1.2rem; }

/* Sidebar */
section[data-testid="stSidebar"] {
  background: #141821 !important;
  border-right: 1px solid var(--border);
}

/* Metrics */
div[data-testid="stMetric"] {
  background: var(--card);
  border: 1px solid var(--border);
  padding: 14px;
  border-radius: 14px;
}

/* Cards */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  padding: 16px;
  border-radius: 16px;
}
.small { color: var(--muted); font-size: 0.9rem; }
.muted2 { color: var(--muted2); font-size: 0.85rem; }

/* Buttons */
div.stButton > button, div.stDownloadButton > button {
  background: var(--gold) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: #101216 !important;
  border-radius: 12px !important;
  padding: 0.6rem 0.9rem !important;
}
div.stButton > button:hover, div.stDownloadButton > button:hover {
  filter: brightness(1.05);
}

/* Inputs */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] div[role="combobox"] {
  background: var(--panel) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 12px !important;
}

/* Dataframe */
div[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
}

</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers
# -----------------------------
def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default



def _format_inr(n: float) -> str:
    """Indian numbering format (₹ 12,34,567)."""
    try:
        n = float(n)
    except Exception:
        return "0"
    neg = n < 0
    n = abs(n)
    s = f"{n:.0f}"
    if len(s) <= 3:
        out = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        out = ",".join(parts + [last3])
    return ("-" if neg else "") + out


def _format_compact_inr(n: float) -> str:
    """Compact INR (₹ 12.4 L / ₹ 1.2 Cr)."""
    try:
        n = float(n)
    except Exception:
        return "₹0"
    absn = abs(n)
    if absn >= 1e7:
        return f"₹{n/1e7:.2f} Cr"
    if absn >= 1e5:
        return f"₹{n/1e5:.2f} L"
    return f"₹{_format_inr(n)}"


def _compute_sla(created_at_iso: str, priority: str) -> Dict[str, str]:
    """Return SLA due and remaining strings based on priority."""
    try:
        created = datetime.fromisoformat(created_at_iso)
    except Exception:
        return {"sla_due": "—", "sla_remaining": "—"}
    pr = (priority or "Normal").strip().lower()
    hours = 72
    if pr == "high":
        hours = 48
    elif pr == "critical":
        hours = 24
    due = created + timedelta(hours=hours)
    now = datetime.now()
    remaining = due - now
    rem_hours = remaining.total_seconds() / 3600.0
    if rem_hours < 0:
        rem = f"Overdue by {abs(rem_hours):.1f} hrs"
    else:
        rem = f"{rem_hours:.1f} hrs"
    return {"sla_due": due.strftime("%Y-%m-%d %H:%M"), "sla_remaining": rem}

def _fmt_money(v: Any, currency: str = "₹") -> str:
    # Always return full INR with Indian separators
    return f"{currency}{_format_inr(v)}"


def _to_df_recent(items):
    if not items:
        return pd.DataFrame(columns=["request_id", "created_at", "site_ref", "status"])
    return pd.DataFrame(items)


def _build_cost_breakdown(outputs: Dict[str, Any]) -> pd.DataFrame:
    # cost_engine.compute_cost stores a rich breakdown
    breakdown = outputs.get("cost_breakdown") or outputs.get("breakdown") or {}
    if isinstance(breakdown, list):
        # already rows
        try:
            return pd.DataFrame(breakdown)
        except Exception:
            return pd.DataFrame({"item": [], "cost": []})
    if isinstance(breakdown, dict):
        rows = [{"item": k, "cost": v} for k, v in breakdown.items()]
        return pd.DataFrame(rows)
    return pd.DataFrame({"item": [], "cost": []})


def render_header():
    st.title("FTTP AI Command Center")
    st.caption("Centralized agentic costing • audit-ready • faster Time-to-Market")


# -----------------------------
# Pages
# -----------------------------
def page_dashboard():
    render_header()

    stats = analytics_last_30_days()
    recent = list_recent(200)
    df = _to_df_recent(recent)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Requests (last 30 days)", stats.get("total_30d", 0))
    by_status = stats.get("by_status_30d", {}) or {}
    c2.metric("Pending review", by_status.get("PENDING_REVIEW", 0) + by_status.get("DRAFT", 0))
    c3.metric("Approved", by_status.get("APPROVED", 0))
    avg_tat = stats.get("avg_turnaround_hours_approved_30d")
    c4.metric("Avg turnaround (approved)", f"{avg_tat:.1f} hrs" if avg_tat is not None else "—")

    st.markdown("### Operational overview")

    left, right = st.columns([2, 1])
    with left:
        if not df.empty:
            df_day = df.dropna(subset=["created_at"]).copy()
            df_day["day"] = df_day["created_at"].dt.date
            g = df_day.groupby("day").size().reset_index(name="requests")
            fig = px.line(g, x="day", y="requests", markers=True, title="Request volume (last 200 records)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No requests yet. Run a costing to populate the dashboard.")

    with right:
        if by_status:
            pie_df = pd.DataFrame([{"status": k, "count": v} for k, v in by_status.items()])
            fig2 = px.pie(pie_df, names="status", values="count", title="Status mix (last 30 days)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Status mix will appear after at least one request is saved.")

    
    st.markdown("### Request density map")
    try:
        pts = []
        for it in recent[:120]:
            rec = get_request(it["request_id"])
            if not rec:
                continue
            inp = rec.get("inputs") or {}
            lat = inp.get("latitude")
            lon = inp.get("longitude")
            if lat is None or lon is None:
                continue
            pts.append({
                "lat": float(lat),
                "lon": float(lon),
                "status": (rec.get("status") or "DRAFT").upper(),
            })
        if pts:
            pdf = pd.DataFrame(pts)
            layer = pdk.Layer(
                "HeatmapLayer",
                data=pdf,
                get_position="[lon, lat]",
                get_weight=1,
                radiusPixels=50,
            )
            view_state = pdk.ViewState(latitude=float(pdf["lat"].mean()), longitude=float(pdf["lon"].mean()), zoom=4)
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text": "{status}"}))
        else:
            st.caption("No geocoded requests available yet. Run a few assessments with PIN codes to populate the map.")
    except Exception as e:
        st.caption(f"Map unavailable: {e}")

    st.markdown("### Recent requests")
    if df.empty:
        st.write("—")
        return
    df_show = df.copy()
    if "budget_preview" in df_show.columns:
        df_show["budget"] = df_show["budget_preview"].apply(_safe_float).apply(_fmt_money)
    else:
        df_show["budget"] = "—"
    if "final_cost" in df_show.columns:
        df_show["final_cost_fmt"] = df_show["final_cost"].apply(_safe_float).apply(_fmt_money)
    else:
        df_show["final_cost_fmt"] = "—"
    st.dataframe(
        df_show[["request_id", "created_at", "site_ref", "status", "budget", "final_cost_fmt"]].sort_values("created_at", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def page_costing():
    render_header()
    st.markdown("### Network Assessment")

    left, right = st.columns([1.35, 1])

    with left:
        st.markdown(
            '<div class="card"><h3 style="margin:0 0 8px 0;">New Network Assessment</h3><div class="muted2">Configure build parameters and run the agentic workflow.</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(" ")

        c1, c2 = st.columns(2)

        with c1:
            postcode = st.text_input("Postal Code / Site Ref (PIN)", value="", placeholder="e.g., 400001")
            distance_m = st.number_input("Fibre Distance (m)", min_value=10, max_value=20000, value=500, step=10)
            premises = st.number_input("Premises Passed", min_value=1, max_value=5000, value=68, step=1)

        with c2:
            location_type = st.selectbox("Location Type", ["Urban", "Semi-Urban", "Rural"], index=0)
            terrain = st.selectbox("Terrain Difficulty", ["Normal", "Difficult", "Extreme"], index=0)
            traffic_mgmt = st.selectbox("Traffic Management", ["Standard", "High", "Critical"], index=0)

        c3, c4 = st.columns(2)
        with c3:
            contractor = st.selectbox("Contractor Strategy", ["In-house", "Partner", "Hybrid"], index=0)
        with c4:
            priority = st.selectbox("Urgency", ["Normal", "High", "Critical"], index=0)

        requester_role = "System User"

        # Budget preview (deterministic, no LLM). Updates as inputs change.
        _base_preview = {
            "distance": float(distance_m),
            "premises": int(premises),
            "build_type": location_type,
            "terrain": terrain,
            "traffic_mgmt": traffic_mgmt,
            "contractor": contractor,
            "priority": priority,
        }
        _scens = scenario_estimates(_base_preview)
        _budget_val = 0.0
        _budget_scen = "—"
        if _scens:
            _best = sorted(_scens, key=lambda x: (x.get("final_cost", 0), x.get("risk_multiplier", 1.0)))[0]
            _budget_val = float(_best.get("final_cost", 0) or 0)
            _budget_scen = str(_best.get("method", "Scenario"))

        st.markdown(" ")
        st.markdown(
            f'<div class="card"><div class="muted2">Budget estimate (preview)</div><div style="font-size:28px;font-weight:700;">{_fmt_money(_budget_val)}</div><div class="muted2">Scenario: <b>{_budget_scen}</b></div></div>',
            unsafe_allow_html=True,
        )

        st.markdown(" ")
        b1, b2 = st.columns(2)
        with b1:
            save_draft = st.button("Save Draft", use_container_width=True)
        with b2:
            submitted = st.button("Run AI Assessment", use_container_width=True)

    # Right panel: map + nearby providers
    lat: Optional[float] = None
    lon: Optional[float] = None
    loc_note = ""
    providers: List[Provider] = []

    with right:
        st.markdown('<div class="card"><h3 style="margin:0 0 10px 0;">Location Overview</h3></div>', unsafe_allow_html=True)

        if postcode.strip():
            try:
                loc = get_location_details(postcode.strip())
                if loc:
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    loc_note = f"{loc.get('city','')}, {loc.get('state','')}, {loc.get('country','')}".strip(", ")
            except Exception:
                loc_note = "Geocoding unavailable for this input."

        if lat is not None and lon is not None:
            providers = find_nearby_providers(lat, lon, k=3)
            m = folium.Map(location=[lat, lon], zoom_start=12, control_scale=True, tiles="OpenStreetMap")
            folium.CircleMarker(
                [lat, lon], radius=6, color="#ffffff", fill=True, fill_opacity=1.0, popup="Assessment Location"
            ).add_to(m)

            for p in providers:
                folium.Marker(
                    [p.lat, p.lon],
                    tooltip=f"{p.name} ({p.distance_km:.1f} km)",
                    icon=folium.Icon(color=p.marker_color, icon="signal", prefix="fa"),
                ).add_to(m)

            st_folium(m, width=None, height=360)
            if loc_note:
                st.caption(loc_note)

            st.markdown(
                '<div class="card"><b>Nearby Providers</b><div class="small">Nearest telecom operators from the reference dataset.</div></div>',
                unsafe_allow_html=True,
            )
            for p in providers:
                st.markdown(
                    f"<div class='card' style='margin-top:10px;'>"
                    f"<b>{p.name}</b> <span class='small' style='float:right;'>{p.distance_km:.1f} km</span><br/>"
                    f"<span class='small'>{p.note}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("Enter a PIN code to preview the map and nearby providers.")

    # Save draft: stores entered inputs + budget preview to MongoDB for traceability.
    if save_draft and not submitted:
        state = {
            "distance": float(distance_m),
            "premises": int(premises),
            "build_type": location_type,
            "terrain": terrain,
            "contractor": contractor,
            "traffic": traffic_mgmt,
            "priority": priority,
            "site_ref": postcode.strip() or "Unknown",
            "requester": requester_role,
            "latitude": lat,
            "longitude": lon,
            "nearby_providers": [p.model_dump() for p in providers] if providers else [],
        "budget_preview": float(_budget_val),
        "budget_scenario": str(_budget_scen),
            "budget_preview": float(_budget_val),
            "budget_scenario": str(_budget_scen),
        }
        draft_request_id = f"DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            save_request(
                request_id=draft_request_id,
                site_ref=state.get("site_ref", "Unknown"),
                inputs=state,
                outputs={"budget_estimate": float(_budget_val), "budget_scenario": str(_budget_scen)},
                status="DRAFT",
            )
            st.success(f"Draft saved. Request ID: {draft_request_id}")
        except Exception as e:
            st.error(f"Draft save failed: {e}")
        return

    # Validating inputs
    if submitted:
        # Clear previous result if new run
        st.session_state.pop("costing_result", None)
        st.session_state.pop("costing_state", None)
        
        state = {
            "distance": float(distance_m),
            "premises": int(premises),
            "build_type": location_type,
            "terrain": terrain,
            "contractor": contractor,
            "traffic": traffic_mgmt,
            "priority": priority,
            "site_ref": postcode.strip() or "Unknown",
            "requester": requester_role,
            "latitude": lat,
            "longitude": lon,
            "nearby_providers": [p.model_dump() for p in providers] if providers else [],
        }

        with st.spinner("Running agentic workflow (decision → costing → risk → simulation)…"):
            result = execute_agent(state)
            st.session_state["costing_result"] = result
            st.session_state["costing_state"] = state
            
    # Check if we have a result in session state to display
    if "costing_result" in st.session_state:
        result = st.session_state["costing_result"]
        state = st.session_state["costing_state"]
        request_id = result.get("request_id")
        site_ref = state.get("site_ref")

        st.success(f"Assessment complete. Request ID: {request_id}")
        
        # Explicit Save Option
        st.markdown("### Actions")
        col_save, _ = st.columns([1, 2])
        with col_save:
            if st.button("Save to Audit Log", type="primary", use_container_width=True, key=f"save_{request_id}"):
                try:
                    save_request(
                        request_id=request_id,
                        site_ref=site_ref,
                        inputs=state,
                        outputs=result,
                        status="PENDING_REVIEW",
                    )
                    st.toast(f"Request {request_id} saved to Audit Log!")
                    st.success(f"Request {request_id} saved successfully to Audit Log.")
                except Exception as e:
                    st.error(f"Failed to save request: {e}") 
    else:
        if not submitted:
            st.caption("Tip: Run the assessment to see results. You can then choose to save them to the Audit Log.")
            return


    st.markdown("#### Scenario comparison")
    try:
        scenarios = scenario_estimates(state)
        sdf = pd.DataFrame(scenarios)
        if not sdf.empty:
            # Determine recommendation: lowest cost among risk <= 1.5, else lowest risk
            sdf["final_cost"] = sdf["final_cost"].apply(_safe_float)
            sdf["risk_multiplier"] = sdf["risk_multiplier"].apply(_safe_float)
            safe = sdf[sdf["risk_multiplier"] <= 1.5]
            if not safe.empty:
                rec_method = safe.sort_values("final_cost").iloc[0]["method"]
            else:
                rec_method = sdf.sort_values("risk_multiplier").iloc[0]["method"]
            sdf["recommended"] = sdf["method"].apply(lambda m: "Yes" if m == rec_method else "")
            sdf = sdf.rename(columns={"method":"Build method","final_cost":"Final cost","risk_multiplier":"Risk mult.","confidence_score":"Confidence","total_days":"Deploy days","recommended":"Recommended"})
            sdf["Final cost"] = sdf["Final cost"].apply(lambda x: _fmt_money(x))
            st.dataframe(sdf, use_container_width=True, hide_index=True)
            st.caption(f"Recommended scenario: {rec_method}")
    except Exception as e:
        st.warning(f"Scenario comparison unavailable: {e}")

    # Cost Comparison (Calculated vs Optimized)
    st.markdown("#### Cost Optimization Analysis")
    
    # 1. Calculated / Base Cost (from best deterministic scenario)
    base_cost = state.get("budget_preview", 0.0) # We stored this in state earlier
    if not base_cost and _base_preview:
         # Fallback re-calc if missing in state
         _scens_redo = scenario_estimates(_base_preview)
         if _scens_redo:
             _best_redo = sorted(_scens_redo, key=lambda x: (x.get("final_cost", 0), x.get("risk_multiplier", 1.0)))[0]
             base_cost = float(_best_redo.get("final_cost", 0))

    # 2. Optimized Cost (from LLM Agent result)
    optimized_cost = result.get("final_cost", result.get("total_cost", 0))

    # 3. Calculate Deltas
    try:
        savings = base_cost - optimized_cost
        savings_pct = (savings / base_cost * 100) if base_cost > 0 else 0.0
    except:
        savings = 0
        savings_pct = 0

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        st.metric("Standard Calculated Cost", _fmt_money(base_cost), help="Best deterministic scenario estimate")
    with cc2:
        st.metric("LLM Optimized Cost", _fmt_money(optimized_cost), delta=f"{savings_pct:.1f}%", delta_color="inverse", help="Final estimate after agentic risk & optimization analysis")
    with cc3:
        st.metric("Potential Savings", _fmt_money(savings), delta="Optimization Impact", help="Difference between standard and optimized costs")

    st.divider()


    # Display outputs
    top = st.columns([2, 1])
    with top[0]:
        st.markdown("#### Summary")
        final_cost = result.get("final_cost", result.get("total_cost", 0))
        st.markdown(
            f"""
<div class="card">
<b>Total estimate:</b> {_fmt_money(final_cost)}<br/>
<span class="small">Build method: <b>{result.get('build_method','Hybrid')}</b> • Confidence: {result.get('build_method_confidence',0.5):.2f} • Survey required: {bool(result.get('survey_required', False))}</span>
</div>
""",
            unsafe_allow_html=True,
        )
        if loc_note:
            st.caption(f"Location context: {loc_note}")

    with top[1]:
        st.markdown("#### Next actions")
        # actor = st.text_input("Your name (for audit actions)", value="")
        actor = "Admin"
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("Mark Reviewed", use_container_width=True):
                update_status(request_id, "REVIEWED", actor=actor, notes="Reviewed in costing screen.")
                st.toast("Marked REVIEWED")
        with a2:
            if st.button("Approve", use_container_width=True):
                update_status(request_id, "APPROVED", actor=actor, notes="Approved in costing screen.")
                st.toast("Marked APPROVED")
        with a3:
            if st.button("Needs Survey", use_container_width=True):
                update_status(request_id, "NEEDS_SURVEY", actor=actor, notes="Survey required before finalization.")
                st.toast("Marked NEEDS_SURVEY")


        st.markdown(" ")
        # Reports
        try:
            pdf_bytes = generate_costing_pack_pdf(
                request_id=request_id,
                site_ref=site_ref,
                inputs=state,
                outputs={**result, "status": "PENDING_REVIEW"},
                generated_by=actor or requester_role or "",
            )
            st.download_button(
                "Download Costing Pack (PDF)",
                data=pdf_bytes,
                file_name=f"FTTP_CostingPack_{request_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"PDF generation unavailable: {e}")

        try:
            opt_pdf = generate_optimization_pack_pdf(
                request_id=request_id,
                site_ref=site_ref,
                inputs=state,
                outputs={**result, "status": "PENDING_REVIEW"},
                generated_by=actor or requester_role or "",
            )
            st.download_button(
                "Download Optimization Pack (PDF)",
                data=opt_pdf,
                file_name=f"FTTP_Optimization_{request_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Optimization PDF unavailable: {e}")

    st.markdown("#### Cost breakdown")
    cost_df = _build_cost_breakdown(result)
    if cost_df.empty:
        st.info("No itemized breakdown found in output. (You can extend cost_engine.compute_cost to emit cost_breakdown.)")
    else:
        # normalize columns
        if "cost" not in cost_df.columns:
            for cand in ["value", "amount", "gbp"]:
                if cand in cost_df.columns:
                    cost_df = cost_df.rename(columns={cand: "cost"})
        cost_df["cost"] = cost_df["cost"].apply(_safe_float)
        st.dataframe(cost_df.sort_values("cost", ascending=False), use_container_width=True, hide_index=True)

        fig = px.pie(cost_df, names="item", values="cost", title="Cost composition")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Risks & assumptions")

    with st.expander("AI explanation and traceability"):
        st.markdown('<div class="card"><b>Agent execution summary</b><br/>'
                    f"<span class='small'>Build method agent: {result.get('build_method','—')} (conf {result.get('build_method_confidence',0.0):.2f})</span><br/>"
                    f"<span class='small'>Cost validation: {result.get('cost_validation','—')}</span><br/>"
                    f"<span class='small'>Risk multiplier: {result.get('risk_multiplier','—')} • Confidence score: {result.get('confidence_score','—')}</span><br/>"
                    f"<span class='small'>LLM validation: {result.get('validation','—')}</span><br/>"
                    '</div>', unsafe_allow_html=True)
        st.caption("Numbers come from the cost catalogue and deterministic calculators. LLM outputs are limited to decisions, explanations, and recommendations.")

    r1, r2 = st.columns(2)
    with r1:
        st.markdown('<div class="card"><b>Top risk</b><br/>{}</div>'.format(result.get("top_risk", "—")), unsafe_allow_html=True)
        st.caption(result.get("risk_mitigation", ""))
    with r2:
        assumptions = result.get("assumptions") or []
        if assumptions:
            st.markdown('<div class="card"><b>Assumptions</b><br/>{}</div>'.format("<br/>".join([f"• {a}" for a in assumptions[:8]])), unsafe_allow_html=True)
        else:
            st.markdown('<div class="card"><b>Assumptions</b><br/>—</div>', unsafe_allow_html=True)

    st.markdown("#### Cost optimization")
    opt_text = result.get("cost_optimization") or "—"
    opt_html = str(opt_text).replace("\n", "<br/>")
    st.markdown(f"<div class='card'><b>Recommendations</b><br/>{opt_html}</div>", unsafe_allow_html=True)


def page_approvals():
    render_header()
    st.markdown("### Audit Log")

    statuses = ["ALL", "PENDING_REVIEW", "REVIEWED", "NEEDS_SURVEY", "APPROVED", "REJECTED", "DRAFT"]
    sel = st.selectbox("Filter by status", statuses, index=0)

    if sel == "ALL":
        items = list_recent(200)
    else:
        items = list_by_status(sel, 200)

    df = pd.DataFrame(items) if items else pd.DataFrame(columns=["request_id", "created_at", "site_ref", "status"])
    # Enrich table with priority, cost, build method, SLA remaining
    if not df.empty:
        pri = []
        bud = []
        cost = []
        bm = []
        sla_rem = []
        for rid, created_at, site_ref, status, *rest in df.itertuples(index=False, name=None):
            rec = get_request(str(rid))
            inp = (rec.get("inputs") or {}) if rec else {}
            out = (rec.get("outputs") or {}) if rec else {}
            pr = inp.get("priority", "")
            pri.append(pr)
            bud.append(inp.get("budget_preview", inp.get("budget_estimate", "")))
            fc = out.get("approved_final_cost", out.get("final_cost", out.get("total_cost", "")))
            cost.append(fc)
            bm.append(out.get("build_method", ""))
            sla = _compute_sla(rec.get("created_at","") if rec else str(created_at), pr)
            sla_rem.append(sla.get("sla_remaining"))
        df["priority"] = pri
        df["budget_preview"] = bud
        df["final_cost"] = cost
        df["build_method"] = bm
        df["sla_remaining"] = sla_rem
        # Sort by priority then SLA
        pr_order = {"Critical": 0, "High": 1, "Normal": 2, "": 3}
        df["_pr"] = df["priority"].map(lambda x: pr_order.get(str(x), 3))
        df = df.sort_values(["_pr", "created_at"], ascending=[True, False]).drop(columns=["_pr"])

    if not df.empty and "budget_preview" in df.columns:
        df["budget_fmt"] = df["budget_preview"].apply(_safe_float).apply(_fmt_money)
    else:
        df["budget_fmt"] = "—"
    if not df.empty and "final_cost" in df.columns:
        df["final_cost_fmt"] = df["final_cost"].apply(_safe_float).apply(_fmt_money)
    else:
        df["final_cost_fmt"] = "—"

    show_cols = ["request_id", "created_at", "site_ref", "status", "priority", "sla_remaining", "budget_fmt", "final_cost_fmt", "build_method"]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

    cexp1, cexp2, cexp3 = st.columns(3)
    with cexp1:
        st.download_button("Export Audit Log (CSV)", data=df.to_csv(index=False).encode('utf-8'), file_name="audit_log.csv", mime="text/csv", use_container_width=True)
    with cexp2:
        df_app = df[df.get('status','').astype(str).str.upper()=="APPROVED"] if not df.empty else df
        st.download_button("Export Approved (CSV)", data=df_app.to_csv(index=False).encode('utf-8'), file_name="audit_log_approved.csv", mime="text/csv", use_container_width=True)
    with cexp3:
        # Monthly report based on current table
        try:
            month_label = datetime.now().strftime('%Y-%m')
            pdfm = generate_monthly_summary_pdf(month_label=month_label, rows=df.to_dict(orient='records'))
            st.download_button("Download Monthly Summary (PDF)", data=pdfm, file_name=f"FTTP_Audit_Summary_{month_label}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.caption(f"Monthly PDF unavailable: {e}")

    st.markdown("#### Review a request")
    req_id = st.text_input("Enter Request ID", value="")
    if not req_id:
        st.caption("Copy a request_id from the table above to review and take action.")
        return

    record = get_request(req_id.strip())
    
    if not record:
        st.error("Request not found.")
        return

    # SLA based on request priority
    try:
        pr = (record.get("inputs") or {}).get("priority", "Normal")
        sla = _compute_sla(record.get("created_at",""), pr)
        record["sla_due"] = sla.get("sla_due")
        record["sla_remaining"] = sla.get("sla_remaining")
    except Exception:
        record["sla_due"] = "—"
        record["sla_remaining"] = "—"

    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("**Request details**")
        st.json(
            {
                "request_id": record["request_id"],
                "created_at": record["created_at"],
                "site_ref": record["site_ref"],
                "status": record["status"],
                "reviewer": record.get("reviewer"),
                "approved_by": record.get("approved_by"),
                "priority": (record.get("inputs") or {}).get("priority"),
                "sla_due": record.get("sla_due"),
                "sla_remaining": record.get("sla_remaining"),
            }
        )
        st.markdown("**Outputs (summary)**")
        outputs = record.get("outputs") or {}
        st.json(
            {
                "final_cost": outputs.get("final_cost", outputs.get("total_cost")),
                "build_method": outputs.get("build_method"),
                "survey_required": outputs.get("survey_required"),
                "top_risk": outputs.get("top_risk"),
                "confidence_score": outputs.get("confidence_score"),
            }
        )

        st.markdown("**Costing pack**")
        try:
            pdf_bytes = generate_costing_pack_pdf(
                request_id=record["request_id"],
                site_ref=record["site_ref"],
                inputs=record.get("inputs") or {},
                outputs={**(record.get("outputs") or {}), "status": record.get("status")},
                generated_by=record.get("reviewer") or record.get("approved_by") or "",
                generated_at_iso=record.get("created_at"),
            )
            st.download_button(
                "Download Costing Pack (PDF)",
                data=pdf_bytes,
                file_name=f"FTTP_CostingPack_{record['request_id']}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"PDF generation unavailable: {e}")

    with c2:
        # role = st.session_state.get("user_role", "Planner")
        # actor = st.text_input("Actor", value=st.session_state.get("actor_name","") or record.get("reviewer") or record.get("approved_by") or "")
        actor = "Admin"
        notes = st.text_area("Notes (optional)", value="", height=120)

        # can_review = role in {"Reviewer", "Manager"}
        # can_approve = role in {"Manager"}
        can_review = True
        can_approve = True

        # Manager can override approved final cost (feedback learning)
        outputs = record.get("outputs") or {}
        current_cost = outputs.get("approved_final_cost", outputs.get("final_cost", outputs.get("total_cost", 0)) or 0)
        override_cost = None
        if can_approve:
            override_cost = st.number_input("Approved Final Cost (₹)", min_value=0.0, value=float(current_cost), step=1000.0)
            st.caption("If adjusted, this value is stored as feedback for learning and reporting.")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Set REVIEWED", use_container_width=True, disabled=not can_review):
                update_status(req_id, "REVIEWED", actor=actor, notes=notes)
                st.success("Updated to REVIEWED")
        with b2:
            if st.button("Set APPROVED", use_container_width=True, disabled=not can_approve):
                if override_cost is not None and float(override_cost) != float(current_cost):
                    patch_output(req_id, {"approved_final_cost": float(override_cost), "approved_cost_override": True})
                update_status(req_id, "APPROVED", actor=actor, notes=notes)
                st.success("Updated to APPROVED")

        b3, b4 = st.columns(2)
        with b3:
            if st.button("Set NEEDS_SURVEY", use_container_width=True, disabled=not can_review):
                update_status(req_id, "NEEDS_SURVEY", actor=actor, notes=notes)
                st.success("Updated to NEEDS_SURVEY")
        with b4:
            if st.button("Reject", use_container_width=True, disabled=not can_review):
                update_status(req_id, "REJECTED", actor=actor, notes=notes)
                st.success("Updated to REJECTED")

        # if role == "Manager":
        if True:
            with st.expander("Admin: Cost Catalog", expanded=False):
                st.caption("Upload a new cost catalog (JSON). This replaces the active catalog for new assessments.")
                up = st.file_uploader("Upload cost_catalog.json", type=["json"])
                if up is not None:
                    try:
                        new_catalog = json.load(up)
                        if not isinstance(new_catalog, dict) or "unit_costs" not in new_catalog:
                            st.error("Invalid catalog. Expected a JSON object with a unit_costs field.")
                        else:
                            backup_dir = "cost_catalog_versions"
                            os.makedirs(backup_dir, exist_ok=True)
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ver_path = os.path.join(backup_dir, f"cost_catalog_{ts}.json")
                            with open(ver_path, "w", encoding="utf-8") as f:
                                json.dump(new_catalog, f, ensure_ascii=False, indent=2)
                            with open("cost_catalog.json", "w", encoding="utf-8") as f:
                                json.dump(new_catalog, f, ensure_ascii=False, indent=2)
                            st.success(f"Catalog updated. Saved version: {ver_path}")
                    except Exception as e:
                        st.error(f"Upload failed: {e}")
    st.markdown("#### Notes / audit trail")
    st.text(record.get("notes", "") or "—")


def page_roi():
    render_header()
    st.markdown("### ROI Calculator")

    observed = roi_observed_metrics(days=30)
    with st.expander("Use observed usage (last 30 days)", expanded=True):
        st.write(
            {
                "requests": observed.get("requests"),
                "estimated_requests_per_month": observed.get("estimated_requests_per_month"),
                "avg_final_cost": observed.get("avg_final_cost"),
                "avg_turnaround_hours_approved": observed.get("avg_turnaround_hours_approved"),
            }
        )
        use_observed_volume = st.checkbox(
            "Prefill requests/month from observed volume", value=True
        )


    st.markdown("#### Observed history (daily snapshots)")
    try:
        snaps = list_roi_snapshots(limit=60)
        if snaps:
            hdf = pd.DataFrame([{"date": s.get("date"),
                                "requests_30d": (s.get("observed_30d") or {}).get("requests"),
                                "avg_final_cost": (s.get("observed_30d") or {}).get("avg_final_cost")}
                               for s in snaps])
            hdf["date"] = pd.to_datetime(hdf["date"], errors="coerce")
            hdf = hdf.dropna(subset=["date"]).sort_values("date")
            if not hdf.empty:
                fig_h = px.line(hdf, x="date", y="requests_30d", markers=True, title="Requests observed in last 30 days (snapshot trend)")
                st.plotly_chart(fig_h, use_container_width=True)
                fig_c = px.line(hdf, x="date", y="avg_final_cost", markers=True, title="Average final cost (₹) – snapshot trend")
                st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.caption("No history yet. It will build automatically as you run assessments.")
    except Exception as e:
        st.caption(f"History unavailable: {e}")

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown("#### Inputs")
        default_req = int(observed.get("estimated_requests_per_month") or 900) if use_observed_volume else 900
        req_per_month = st.number_input("Requests per month", min_value=1, max_value=20000, value=default_req, step=10)
        manual_hours = st.number_input("Manual effort per request (hours)", min_value=0.1, max_value=20.0, value=2.0, step=0.1)
        ai_hours = st.number_input("With AI tool effort per request (hours)", min_value=0.05, max_value=20.0, value=0.33, step=0.01)
        hourly_cost = st.number_input("Fully-loaded labour cost (₹/hour)", min_value=1, max_value=20000, value=450, step=10)

        st.markdown("#### Quality impact (optional)")
        obs_avg = int(observed.get("avg_final_cost") or 2_000_000)
        avg_estimate = st.number_input("Avg estimated build cost per request (₹)", min_value=0, max_value=50_000_000, value=obs_avg, step=50_000)
        manual_error_rate = st.slider("Manual estimation error rate (%)", min_value=0.0, max_value=20.0, value=5.0, step=0.5)
        error_reduction = st.slider("AI reduces error by (%)", min_value=0.0, max_value=80.0, value=20.0, step=1.0)

        st.markdown("#### Tool cost")
        build_cost = st.number_input("One-time build/integration cost (₹)", min_value=0, max_value=200_000_000, value=30_000_000, step=1_000_000)
        run_cost = st.number_input("Annual run/maintenance cost (₹)", min_value=0, max_value=200_000_000, value=6_000_000, step=250_000)

    st.markdown("---")
    st.markdown("### Network Monetization ROI")
    
    nm_col1, nm_col2 = st.columns([1.2, 1])
    with nm_col1:
        st.caption("Link a specific assessment to calculate build ROI.")
        linked_req_id = st.text_input("Link Network Assessment (Request ID)", placeholder="e.g. req_12345")
        
        # Defaults
        def_premises = 1000
        def_capex = 5_000_000.0
        
        if linked_req_id:
             r = get_request(linked_req_id.strip())
             if r:
                 inps = r.get("inputs") or {}
                 outs = r.get("outputs") or {}
                 def_premises = int(inps.get("premises") or 1000)
                 def_capex = float(outs.get("final_cost") or outs.get("total_cost") or 5_000_000.0)
                 st.success(f"Loaded: {def_premises} premises, {_fmt_money(def_capex)} capex")
             else:
                 st.warning("Request ID not found. Using defaults.")

        st.markdown("#### Build Assumptions")
        hp = st.number_input("Homes Passed (Premises)", min_value=1, value=def_premises, step=10)
        capex = st.number_input("Total Capex (₹)", min_value=0.0, value=def_capex, step=100_000.0)
        takeup = st.slider("Take-up Rate (%)", 0, 100, 25, 1)
        arpu = st.number_input("ARPU (₹/month)", min_value=0, value=800, step=50)
        opex_pct = st.slider("OpEx (% of revenue)", 0, 100, 20, 1)

    # Monetization Calcs
    users = int(hp * (takeup / 100.0))
    monthly_rev = users * arpu
    annual_rev = monthly_rev * 12
    annual_opex = annual_rev * (opex_pct / 100.0)
    annual_ebitda = annual_rev - annual_opex
    
    simple_payback_months = (capex / (annual_ebitda / 12)) if (annual_ebitda > 0) else None

    with nm_col2:
        st.markdown("#### Financial Outcomes")
        st.metric("Connected Users", f"{users} / {hp}")
        st.metric("Annual Revenue", _fmt_money(annual_rev))
        st.metric("Annual EBITDA", _fmt_money(annual_ebitda), delta=f"{((annual_ebitda/annual_rev)*100):.1f}% Margin" if annual_rev > 0 else None)
        st.metric("Simple Payback", f"{simple_payback_months:.1f} months" if simple_payback_months else "Never")

    # Cash Flow Chart
    years = 5
    cumulative = [-capex]
    for y in range(1, years + 1):
        cumulative.append(cumulative[-1] + annual_ebitda)
    
    cf_df = pd.DataFrame({
        "Year": range(0, years + 1),
        "Cash Flow": cumulative
    })
    fig_cf = px.line(cf_df, x="Year", y="Cash Flow", markers=True, title=f"Cumulative Cash Flow ({years} Year Horizon)")
    fig_cf.add_hline(y=0, line_dash="dash", line_color="green")
    st.plotly_chart(fig_cf, use_container_width=True)


    # Calculations
    monthly_manual = req_per_month * manual_hours * hourly_cost
    monthly_ai = req_per_month * ai_hours * hourly_cost
    annual_labour_savings = (monthly_manual - monthly_ai) * 12

    # Error variance: estimated monthly spend * error% * reduction%
    monthly_estimated_total = req_per_month * avg_estimate
    monthly_variance = monthly_estimated_total * (manual_error_rate / 100.0)
    annual_avoidance = monthly_variance * (error_reduction / 100.0) * 12

    annual_net_benefit = annual_labour_savings + annual_avoidance - run_cost
    payback_months = None
    if annual_net_benefit > 0:
        payback_months = (build_cost / annual_net_benefit) * 12

    with right:
        st.markdown("#### Results")
        c1, c2 = st.columns(2)
        c1.metric("Annual labour savings", _fmt_money(annual_labour_savings))
        c2.metric("Annual error avoidance", _fmt_money(annual_avoidance))

        st.metric("Annual net benefit (after run cost)", _fmt_money(annual_net_benefit))
        st.metric("Payback period", f"{payback_months:.1f} months" if payback_months is not None else "—")

        st.markdown("#### Summary chart")
        chart_df = pd.DataFrame(
            [
                {"category": "Labour savings", "value": annual_labour_savings},
                {"category": "Error avoidance", "value": annual_avoidance},
                {"category": "Annual run cost", "value": -run_cost},
            ]
        )
        fig = px.bar(chart_df, x="category", y="value", title="Annualized ROI components (₹)")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Board-ready bullets")
        bullets = [
            f"Current manual run-rate: {_fmt_money(monthly_manual)}/month → {_fmt_money(monthly_manual*12)}/year",
            f"With AI tool run-rate: {_fmt_money(monthly_ai)}/month → {_fmt_money(monthly_ai*12)}/year",
            f"Estimated annual value: {_fmt_money(annual_labour_savings + annual_avoidance)} (before run cost)",
            f"Net benefit after run cost: {_fmt_money(annual_net_benefit)}",
        ]
        st.markdown("<div class='card'>" + "<br/>".join([f"• {b}" for b in bullets]) + "</div>", unsafe_allow_html=True)

        st.markdown("#### Download")
        try:
            roi_inputs = {
                "requests_per_month": req_per_month,
                "manual_hours_per_request": manual_hours,
                "ai_hours_per_request": ai_hours,
                "labour_cost_per_hour": hourly_cost,
                "avg_estimated_build_cost": avg_estimate,
                "manual_error_rate_pct": manual_error_rate,
                "error_reduction_pct": error_reduction,
                "one_time_build_cost": build_cost,
                "annual_run_cost": run_cost,
                "network_monetization": {
                    "linked_req_id": linked_req_id,
                    "premises_passed": hp,
                    "capex": capex,
                    "takeup_rate_pct": takeup,
                    "arpu": arpu,
                    "opex_pct_revenue": opex_pct,
                    "connected_users": users,
                    "annual_revenue": annual_rev,
                    "annual_ebitda": annual_ebitda,
                    "simple_payback_months": simple_payback_months,
                }
            }
            roi_outputs = {
                "annual_labour_savings": annual_labour_savings,
                "annual_error_avoidance": annual_avoidance,
                "annual_run_cost": run_cost,
                "annual_net_benefit": annual_net_benefit,
                "payback_months": round(payback_months, 1) if payback_months is not None else None,
                "bullets": bullets,
            }
            pdf = generate_roi_report_pdf(
                title="FTTP AI Command Center – ROI Report",
                observed=observed,
                inputs=roi_inputs,
                outputs=roi_outputs,
            )
            st.download_button(
                "Download ROI Report (PDF)",
                data=pdf,
                file_name="FTTP_ROI_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"ROI PDF unavailable: {e}")


# -----------------------------
# Navigation
# -----------------------------
st.sidebar.markdown("## FTTP AI Command Center")

# Session role (simple governance simulation)
# Session role (simple governance simulation)
# role = st.sidebar.selectbox("Role", ["Planner", "Reviewer", "Manager"], index=0, key="user_role")
# st.sidebar.text_input("Your name", value=st.session_state.get("actor_name",""), key="actor_name")
st.session_state["user_role"] = "Manager"
st.session_state["actor_name"] = "Admin"

# Currency display preference (Removed, default INR)
# st.sidebar.selectbox("Currency display", ["INR", "COMPACT"], index=0, key="money_mode")

page = st.sidebar.radio("Navigate", ["Dashboard", "Network Assessment", "Audit Log", "ROI Calculator"], index=0)

if page == "Dashboard":
    page_dashboard()
elif page == "Network Assessment":
    page_costing()
elif page == "Audit Log":
    page_approvals()
else:
    page_roi()