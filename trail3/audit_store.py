import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import json

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.collection import Collection
    HAS_MONGO = True
except ImportError:
    HAS_MONGO = False

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "fttp_audit_db")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "requests")
ROI_COLLECTION_NAME = os.getenv("MONGO_ROI_COLLECTION", "roi_history")
STRICT_MONGO = os.getenv("STRICT_MONGO", "0").strip() == "1"

_client = None
_db = None
_collection = None

def _get_collection() -> Optional[Collection]:
    global _client, _db, _collection
    if not HAS_MONGO:
        return None
    
    if _collection is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            _db = _client[DB_NAME]
            _collection = _db[COLLECTION_NAME]
            
            # Ensure indexes
            _collection.create_index([("request_id", ASCENDING)], unique=True)
            _collection.create_index([("created_at", DESCENDING)])
            _collection.create_index([("status", ASCENDING)])
            _collection.create_index([("approved_at", DESCENDING)])
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            if STRICT_MONGO:
                raise
            return None
    return _collection

def save_request(
    request_id: str,
    site_ref: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    status: str = "DRAFT",
) -> None:
    # Helper for serialization
    def _json_safe(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
             return obj.model_dump()
        if hasattr(obj, "dict"):
             return obj.dict()
        return str(obj)

    # Ensure clean dicts
    try:
        inputs_safe = json.loads(json.dumps(inputs, default=_json_safe))
        outputs_safe = json.loads(json.dumps(outputs, default=_json_safe))
    except Exception:
        inputs_safe = inputs
        outputs_safe = outputs

    col = _get_collection()
    
    # Mongo Save
    if col is not None:
        now = datetime.now().isoformat()
        # Upsert logic
        existing = col.find_one({"request_id": request_id}, {"created_at": 1})
        created_at = existing["created_at"] if existing else now

        doc = {
            "request_id": request_id,
            "created_at": created_at,
            "site_ref": site_ref,
            "status": status,
            "input_json": inputs_safe,
            "output_json": outputs_safe,
            "updated_at": now
        }
        
        try:
            col.update_one(
                {"request_id": request_id},
                {"$set": doc},
                upsert=True
            )
            # Update daily ROI snapshot (non-blocking)
            try:
                record_roi_snapshot()
            except Exception:
                pass
            return
        except Exception as e:
            print(f"Mongo save failed: {e}")
            # Fall through to file save if mongo fails

    # File-based Fallback (audit_store.json)
    try:
        store_file = "audit_store.json"
        data = {}
        if os.path.exists(store_file):
            with open(store_file, "r") as f:
                try:
                    data = json.load(f)
                except:
                    data = {}
        
        now = datetime.now().isoformat()
        record = {
            "request_id": request_id,
            "created_at": data.get(request_id, {}).get("created_at", now),
            "site_ref": site_ref,
            "status": status,
            "input_json": inputs_safe,
            "output_json": outputs_safe,
            "updated_at": now
        }
        data[request_id] = record
        
        with open(store_file, "w") as f:
            json.dump(data, f, indent=2)
            
    except Exception as e:
        print(f"File save failed: {e}")
        raise e

def patch_output(request_id: str, patch: Dict[str, Any]) -> None:
    col = _get_collection()
    if col is None:
        return

    # MongoDB supports dot notation for nested updates if we knew the structure,
    # but here we are doing a merge of the 'output_json' dict.
    # For atomic deep merge we might need a pipeline or fetch-merge-save.
    # Simple fetch-merge-save for now.
    
    doc = col.find_one({"request_id": request_id}, {"output_json": 1})
    if not doc:
        return
        
    current_out = doc.get("output_json", {})
    if isinstance(patch, dict):
        current_out.update(patch)
    
    col.update_one(
        {"request_id": request_id},
        {"$set": {"output_json": current_out}}
    )

def update_status(
    request_id: str,
    status: str,
    actor: str = "",
    notes: str = "",
) -> None:
    col = _get_collection()
    if col is None:
        return

    now = datetime.now().isoformat()
    status_upper = (status or "").upper().strip()
    
    update_fields = {"status": status_upper}
    
    if status_upper in {"REVIEWED", "PENDING_REVIEW"}:
        update_fields["reviewer"] = actor or None
        update_fields["reviewed_at"] = now
    
    if status_upper == "APPROVED":
        update_fields["approved_by"] = actor or None
        update_fields["approved_at"] = now
        
    # Append notes logic
    if notes:
        # We can append to a list or simple string concatenation. 
        # To match previous behavior (string concatenation):
        doc = col.find_one({"request_id": request_id}, {"notes": 1})
        existing_notes = (doc.get("notes") or "") if doc else ""
        new_notes = f"{existing_notes}\n{notes}".strip()
        update_fields["notes"] = new_notes

    col.update_one(
        {"request_id": request_id},
        {"$set": update_fields}
    )

def get_request(request_id: str) -> Optional[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        return None
        
    doc = col.find_one({"request_id": request_id})
    if not doc:
        return None
        
    return {
        "request_id": doc.get("request_id"),
        "created_at": doc.get("created_at"),
        "site_ref": doc.get("site_ref"),
        "status": doc.get("status") or "DRAFT",
        "reviewer": doc.get("reviewer"),
        "reviewed_at": doc.get("reviewed_at"),
        "approved_by": doc.get("approved_by"),
        "approved_at": doc.get("approved_at"),
        "notes": doc.get("notes") or "",
        "inputs": doc.get("input_json") or {},
        "outputs": doc.get("output_json") or {},
    }

def list_recent(limit: int = 50) -> List[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        return []
        
    cursor = col.find(
        {}, 
        {"request_id": 1, "created_at": 1, "site_ref": 1, "status": 1, "approved_at": 1, "input_json.budget_preview": 1, "output_json.final_cost": 1, "output_json.total_cost": 1, "output_json.budget_estimate": 1}
    ).sort("created_at", DESCENDING).limit(limit)
    
    return [
        {
            "request_id": d.get("request_id"),
            "created_at": d.get("created_at"),
            "site_ref": d.get("site_ref"),
            "status": d.get("status") or "DRAFT",
            "approved_at": d.get("approved_at"),
            "budget_preview": (d.get("input_json") or {}).get("budget_preview"),
            "final_cost": (d.get("output_json") or {}).get("final_cost", (d.get("output_json") or {}).get("total_cost")),
        }
        for d in cursor
    ]

def list_by_status(status: str, limit: int = 200) -> List[Dict[str, Any]]:
    col = _get_collection()
    if col is None:
        return []
        
    status_upper = (status or "").upper().strip()
    cursor = col.find(
        {"status": status_upper},
        {"request_id": 1, "created_at": 1, "site_ref": 1, "status": 1, "reviewer": 1, "approved_at": 1}
    ).sort("created_at", DESCENDING).limit(limit)
    
    return [
        {
            "request_id": d.get("request_id"),
            "created_at": d.get("created_at"),
            "site_ref": d.get("site_ref"),
            "status": d.get("status") or "DRAFT",
            "reviewer": d.get("reviewer"),
            "approved_at": d.get("approved_at"),
            "budget_preview": (d.get("input_json") or {}).get("budget_preview"),
            "final_cost": (d.get("output_json") or {}).get("final_cost", (d.get("output_json") or {}).get("total_cost")),
        }
        for d in cursor
    ]

def analytics_last_30_days() -> Dict[str, Any]:
    col = _get_collection()
    if col is None:
        return {"total_30d": 0, "by_status_30d": {}, "avg_turnaround_hours_approved_30d": None}
    
    # Calculate 30 days ago using datetime logic might be complex if we store ISO strings.
    # For simplicity, we can fetch more and filter in python, OR use string comparison if ISO format.
    # ISO strings are lexicographically sortable.
    
    cutoff = datetime.now() # We need to subtract 30 days properly
    # But for string comparison, we can just filter by string > cutoff_iso
    # To be safe on imports, let's just use Python filtering for small datasets, 
    # but ideally we use mongo query.
    
    # Approximate "30 days ago" as ISO string? 
    # Let's trust Python's datetime subtraction
    from datetime import timedelta
    cutoff_dt = datetime.now() - timedelta(days=30)
    cutoff_iso = cutoff_dt.isoformat()
    
    cursor = col.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"created_at": 1, "status": 1, "approved_at": 1}
    )
    
    rows = list(cursor)
    total = len(rows)
    by_status = {}
    turnaround_hours = []
    
    for d in rows:
        st = (d.get("status") or "DRAFT").upper()
        by_status[st] = by_status.get(st, 0) + 1
        
        c_str = d.get("created_at")
        a_str = d.get("approved_at")
        
        if c_str and a_str:
            try:
                c = datetime.fromisoformat(c_str)
                a = datetime.fromisoformat(a_str)
                turnaround_hours.append((a - c).total_seconds() / 3600.0)
            except Exception:
                pass
                
    avg_tat = sum(turnaround_hours) / len(turnaround_hours) if turnaround_hours else None
    
    return {
        "total_30d": total,
        "by_status_30d": by_status,
        "avg_turnaround_hours_approved_30d": avg_tat,
    }

def roi_observed_metrics(days: int = 30) -> Dict[str, Any]:
    col = _get_collection()
    if col is None:
         return {
            "period_days": days,
            "requests": 0,
            "estimated_requests_per_month": 0,
            "by_status": {},
            "avg_turnaround_hours_approved": None,
            "avg_final_cost": None,
        }

    from datetime import timedelta
    cutoff_dt = datetime.now() - timedelta(days=days)
    cutoff_iso = cutoff_dt.isoformat()
    
    cursor = col.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"created_at": 1, "status": 1, "approved_at": 1, "output_json": 1}
    )
    
    rows = list(cursor)
    total = len(rows)
    by_status = {}
    turnaround_hours = []
    final_costs = []
    
    for d in rows:
        st = (d.get("status") or "DRAFT").upper()
        by_status[st] = by_status.get(st, 0) + 1
        
        if d.get("approved_at"):
            try:
                c = datetime.fromisoformat(d.get("created_at"))
                a = datetime.fromisoformat(d.get("approved_at"))
                turnaround_hours.append((a - c).total_seconds() / 3600.0)
            except Exception:
                pass
        
        out = d.get("output_json") or {}
        fc = out.get("final_cost", out.get("total_cost", out.get("base_cost")))
        if fc is not None:
            try:
                final_costs.append(float(fc))
            except:
                pass

    avg_tat = sum(turnaround_hours) / len(turnaround_hours) if turnaround_hours else None
    avg_final_cost = sum(final_costs) / len(final_costs) if final_costs else None
    est_monthly_volume = round(total * (30.0 / max(1.0, float(days))))
    
    return {
        "period_days": days,
        "requests": total,
        "estimated_requests_per_month": est_monthly_volume,
        "by_status": by_status,
        "avg_turnaround_hours_approved": avg_tat,
        "avg_final_cost": avg_final_cost,
    }


def _get_roi_collection() -> Optional[Collection]:
    """Separate collection to store daily KPI snapshots for ROI/history charts."""
    col = _get_collection()
    if col is None:
        return None
    try:
        db = col.database
        roi_col = db[ROI_COLLECTION_NAME]
        roi_col.create_index([("date", ASCENDING)], unique=True)
        roi_col.create_index([("created_at", DESCENDING)])
        return roi_col
    except Exception as e:
        print(f"MongoDB ROI collection error: {e}")
        if STRICT_MONGO:
            raise
        return None

def record_roi_snapshot(date_iso: Optional[str] = None) -> None:
    """Upsert a daily snapshot of observed metrics (for ROI/history)."""
    roi_col = _get_roi_collection()
    if roi_col is None:
        return
    from datetime import date
    today = date.today().isoformat() if not date_iso else date_iso
    # Use observed metrics for last 30 days, plus today's counts if needed
    obs = roi_observed_metrics(days=30)
    now = datetime.now().isoformat()
    doc = {
        "date": today,
        "created_at": now,
        "observed_30d": obs,
    }
    roi_col.update_one({"date": today}, {"$set": doc}, upsert=True)

def list_roi_snapshots(limit: int = 90) -> List[Dict[str, Any]]:
    roi_col = _get_roi_collection()
    if roi_col is None:
        return []
    cursor = roi_col.find({}, {"_id": 0}).sort("date", DESCENDING).limit(limit)
    return list(cursor)
