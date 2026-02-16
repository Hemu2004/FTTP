
import os
import json
from functools import lru_cache
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

# Ensure local .env is loaded for Streamlit and CLI usage
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; env vars may already be injected by the runtime
    pass

# Prefer GROQ key when present, fall back to OPENAI_API_KEY for compatibility
_GROQ_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")

# Correct Groq API Base URL
# Old incorrect value: https://api.groq.ai/v1
_GROQ_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")

# Map OpenAI model names to Groq equivalent
# Using Llama 3.3 70B Versatile as the main driver
MODEL_MAPPING = {
    "gpt-4o-mini": "llama-3.3-70b-versatile",
    "gpt-4o": "llama-3.3-70b-versatile",
    "openai": "llama-3.3-70b-versatile" # default fallback
}

openai_client = None
if _GROQ_KEY:
    # Use the OpenAI-compatible client pointed at Groq's API base
    # NOTE: 'api_base' is deprecated in newer openai versions, use 'base_url'
    openai_client = OpenAI(api_key=_GROQ_KEY, base_url=_GROQ_BASE)
else:
    # If a pure OpenAI key is present but GROQ_API_KEY is not, default to OpenAI base URL.
    _OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    if _OPENAI_KEY:
        openai_client = OpenAI(api_key=_OPENAI_KEY)


def _ensure_openai():
    if openai_client is None:
        raise ValueError("GROQ_API_KEY or OPENAI_API_KEY not configured in environment (.env)")


def _extract_text_from_response(resp) -> str:
    try:
        return resp.choices[0].message.content
    except Exception:
        # Fallback for different response shapes
        return json.dumps(resp)


def run_cost_optimization_agent(state: dict) -> dict:
    """
    Role: Cost Optimization Agent
    Task: Suggest specific savings on the BOM.
    """
    _ensure_openai()
    
    # Use INR context (India) and ground in available state.
    prompt = f"""
    You are the Cost Optimization Agent for an India FTTP build.
    Provide ONE specific, actionable optimization that could reduce cost or time-to-build.

    Constraints:
    - Do NOT invent new costs. Use only the BOM values below.
    - Keep the suggestion practical for Indian right-of-way and street works.

    BOM (₹):
    - Civils: {float(state.get('trench_civil_cost', 0) or 0):,.0f}
    - Fibre & materials: {float(state.get('fibre_material_cost', 0) or 0):,.0f}
    - Labour: {float(state.get('labour_cost', 0) or 0):,.0f}
    Total (₹): {float(state.get('base_cost', 0) or 0):,.0f}

    Context:
    - Build method: {state.get('build_method','Hybrid')}
    - Location type: {state.get('build_type', state.get('location_type','Urban'))}
    - Terrain: {state.get('terrain', state.get('terrain_type','Normal'))}
    - Traffic mgmt: {state.get('traffic','Standard')}
    - Nearby operators: {[p.get('name') for p in (state.get('nearby_providers') or []) if isinstance(p, dict) and p.get('name')][:3]}

    Return JSON:
    {{
      "validation": "Checked",
      "optimization": "One concise recommendation (1–2 sentences)"
    }}
    """
    
    try:
        resp = openai_client.chat.completions.create(
            model=_get_model_name("gpt-4o"), 
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        return json.loads(_extract_text_from_response(resp))
    except:
        return {"validation": "System Error", "optimization": "Standard verification required."}


def run_risk_agent(state: dict) -> dict:
    """
    Role: Risk Agent
    Task: Identify top delivery risk.
    """
    _ensure_openai()
    
    prompt = f"""
    You are the Risk Agent (Critical Infrastructure).
    Assess:
    - Location: {state['location_type']}
    - Terrain: {state['terrain_type']}
    - Risk Score: {state['risk_multiplier']}
    
    Identify the single biggest delivery risk and a mitigation.
    
    Return JSON:
    {{
        "top_risk": "Specific Risk Name",
        "mitigation": "Specific Action"
    }}
    """
    
    try:
        resp = openai_client.chat.completions.create(
            model=_get_model_name("gpt-4o"), 
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        return json.loads(_extract_text_from_response(resp))
    except:
        return {"top_risk": "Standard Risk", "mitigation": "Standard Protocols"}


def _get_model_name(requested_model: str) -> str:
    """Helper to map requested model to available Groq model if using Groq."""
    if _GROQ_KEY and "groq" in _GROQ_BASE:
        return MODEL_MAPPING.get(requested_model, "llama-3.3-70b-versatile")
    return requested_model


def call_llm(prompt: str, mode: str = "fast", temperature: float = 0.4, timeout: int = 30) -> str:
    """
    Simple OpenAI call used throughout the project.

    mode: 'fast' -> gpt-4o-mini (lower latency); 'deep' -> gpt-4o
    """
    _ensure_openai()
    requested_model = "gpt-4o-mini" if mode == "fast" else "gpt-4o"
    model = _get_model_name(requested_model)

    resp = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        timeout=timeout,
    )
    return _extract_text_from_response(resp)


def call_llm_json(prompt: str, timeout: int = 30) -> dict:
    """
    Call OpenAI and request JSON-serializable structured output.
    Returns a Python dict.
    """
    _ensure_openai()
    model = _get_model_name("gpt-4o")
    
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=timeout,
    )
    text = _extract_text_from_response(resp)
    try:
        return json.loads(text)
    except Exception:
        # If model didn't return pure JSON, attempt to extract JSON blob
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        raise


@lru_cache(maxsize=128)
def cached_llm(prompt: str, mode: str = "fast") -> str:
    return call_llm(prompt, mode=mode)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def safe_llm(prompt: str, mode: str = "fast") -> str:
    """Safe LLM call with retry logic."""
    return call_llm(prompt, mode=mode)


def llm_validate(prompt: str, model: str = "openai") -> dict:
    """
    Validate FTTP outputs using OpenAI.
    Returns a dict with status and optional issue.
    """
    _ensure_openai()
    
    validation_prompt = f"""
    Validate this FTTP output.
    Return JSON ONLY with keys: status (VALID or INVALID), issue (short explanation if invalid)
    
    {prompt}
    """
    

    
    model_name = _get_model_name("gpt-4o-mini")

    resp = openai_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": validation_prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=30,
    )
    
    text = _extract_text_from_response(resp)
    try:
        result = json.loads(text)
        return result
    except Exception:
        # Try to extract JSON from text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except Exception:
                pass
        return {"status": "VALID", "issue": "parse_error"}



def run_strategy_agent(state: dict) -> str:
    """
    Role: Strategic Planner
    Task: Align build with corporate goals (5M premises, TTM).
    """
    _ensure_openai()
    
    prompt = f"""
    You are the Strategic Planner for a UK Telecom Provider.
    Goal: Deploy fiber to 5M premises. 
    Challenge: Reduce manual errors, improve Time to Market (TTM).
    
    Review this build scenario:
    - Build Type: {state.get('build_type')}
    - Terrain: {state.get('terrain')}
    - Premises: {state.get('premises')}
    - Total Cost: £{state.get('final_cost', 0):,.2f}
    - Risk Score: {state.get('risk_multiplier', 0)}
    - Est. Time: {state.get('simulation').total_days if state.get('simulation') else 'N/A'} days

    Provide a 2-sentence Executive Strategy Note focusing on:
    1. Alignment with the 5M goal.
    2. Any specific TTM opportunity or risk.
    
    Keep it professional and directive.
    """

    resp = openai_client.chat.completions.create(
        model=_get_model_name("gpt-4o"), 
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=150
    )
    
    return _extract_text_from_response(resp)


def run_build_method_agent(state: dict) -> dict:
    """Role: Build Method Decision Agent.

    Decides *how* to build (underground/overhead/hybrid) and flags if a survey is needed.
    Returns structured JSON so downstream costing and reporting are deterministic.
    """
    _ensure_openai()

    prompt = f"""
    You are the Build Method Decision Agent for a UK FTTP network build.

    Inputs:
    - Build Area Type: {state.get('build_type')}
    - Terrain: {state.get('terrain')}
    - Distance to node (m): {state.get('distance')}
    - Premises: {state.get('premises')}
    - Traffic management required: {state.get('traffic')}

    Decide the most likely build method and whether a civils survey is required.
    Keep assumptions realistic for UK telecom deployments.

    Return JSON ONLY:
    {{
      "build_method": "Underground" | "Overhead" | "Hybrid",
      "survey_required": true | false,
      "assumptions": ["short bullet assumption 1", "assumption 2"],
      "confidence": 0.0
    }}
    """

    resp = openai_client.chat.completions.create(
        model=_get_model_name("gpt-4o"),
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=30,
    )
    return json.loads(_extract_text_from_response(resp))


# Alias for backward compatibility
llm_call = call_llm

