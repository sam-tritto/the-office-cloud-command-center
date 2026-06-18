"""
ScrantonOS — Mock Tools (DEV Mode)
====================================
Local file-based fallback implementations for all system tools.
These parse CSV/JSON files from mock_data/ so the entire pipeline
can run without any cloud credentials.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
from collections import Counter
from typing import Any

from config import get_config
from schemas.models import (
    BillingLineItem,
    BillingReport,
    LogAnalysisResult,
    LogEntry,
    TechDebtItem,
    TechDebtReport,
)

MOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "mock_data")


# ═══════════════════════════════════════════════════════════════════════
# Dwight's Tool — Log Analysis
# ═══════════════════════════════════════════════════════════════════════

def fetch_app_logs() -> list[dict[str, Any]]:
    """
    Parse the static crash_logs.csv and return structured log entries.
    Returns a list of dicts suitable for LLM consumption.
    """
    csv_path = os.path.join(MOCK_DIR, "crash_logs.csv")
    entries: list[LogEntry] = []

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(LogEntry(
                timestamp=row["timestamp"],
                severity=row["severity"],
                service=row["service"],
                message=row["message"],
                container_id=row.get("container_id"),
                memory_mb=float(row["memory_mb"]) if row.get("memory_mb") else None,
            ))

    return [e.model_dump() for e in entries]


def analyze_logs_structured(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Pre-compute structured metrics from log entries for Dwight's analysis.
    This is deterministic Python — no LLM involvement.
    """
    total = len(entries)
    severity_counts = Counter(e["severity"] for e in entries)
    service_errors = Counter(e["message"] for e in entries if e["severity"] in ("ERROR", "CRITICAL"))

    # Detect memory leak pattern
    memory_values = [e["memory_mb"] for e in entries if e.get("memory_mb")]
    memory_leak = False
    peak_memory = 0.0
    if memory_values:
        peak_memory = max(memory_values)
        # Simple heuristic: if memory grows monotonically over 5+ samples from same service
        payment_mem = [e["memory_mb"] for e in entries if e.get("service") == "payment-processor" and e.get("memory_mb")]
        if len(payment_mem) >= 5:
            increases = sum(1 for i in range(1, len(payment_mem)) if payment_mem[i] > payment_mem[i - 1])
            memory_leak = increases / (len(payment_mem) - 1) > 0.8

    return {
        "total_entries": total,
        "critical_count": severity_counts.get("CRITICAL", 0),
        "error_count": severity_counts.get("ERROR", 0),
        "warning_count": severity_counts.get("WARNING", 0),
        "memory_leak_detected": memory_leak,
        "peak_memory_mb": peak_memory,
        "top_errors": [msg for msg, _ in service_errors.most_common(5)],
    }


# ═══════════════════════════════════════════════════════════════════════
# Oscar's Tool — Billing Analysis
# ═══════════════════════════════════════════════════════════════════════

def query_billing_data() -> dict[str, Any]:
    """
    Load billing_data.json and return the raw billing dataset.
    """
    json_path = os.path.join(MOCK_DIR, "billing_data.json")
    with open(json_path, "r") as f:
        data = json.load(f)
    return data


def compute_billing_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """
    Pre-compute billing metrics for Oscar's analysis.
    Deterministic Python — identifies cost anomalies and top spenders.
    """
    items = data["line_items"]
    budget = data.get("budget_usd", 12000.0)
    period = data["billing_period"]

    total_cost = sum(item["cost_usd"] for item in items)
    num_days = len(set(item["date"] for item in items))
    daily_avg = total_cost / max(num_days, 1)

    # Aggregate by service
    service_totals: dict[str, float] = {}
    for item in items:
        service_totals[item["service"]] = service_totals.get(item["service"], 0) + item["cost_usd"]

    top_services = sorted(service_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    # Detect anomalies: any single day > 3x daily average
    daily_totals: dict[str, float] = {}
    for item in items:
        daily_totals[item["date"]] = daily_totals.get(item["date"], 0) + item["cost_usd"]

    anomalies = []
    for date, cost in daily_totals.items():
        if cost > daily_avg * 3:
            anomalies.append(f"Spike on {date}: ${cost:.2f} ({cost/daily_avg:.1f}x daily avg)")

    # Check for GPU cost explosion
    gpu_cost = sum(item["cost_usd"] for item in items if "GPU" in item.get("sku_description", ""))
    if gpu_cost > total_cost * 0.3:
        anomalies.append(f"GPU costs are {gpu_cost/total_cost*100:.1f}% of total spend (${gpu_cost:.2f})")

    return {
        "period_start": period["start"],
        "period_end": period["end"],
        "total_cost_usd": round(total_cost, 2),
        "daily_average_usd": round(daily_avg, 2),
        "top_services": [{svc: round(cost, 2)} for svc, cost in top_services],
        "anomalies": anomalies,
        "over_budget": total_cost > budget,
        "budget_utilization_pct": round((total_cost / budget) * 100, 1),
    }


# ═══════════════════════════════════════════════════════════════════════
# Stanley's Tool — IAM Whitelist Check
# ═══════════════════════════════════════════════════════════════════════

def check_iam_whitelist(role: str) -> dict[str, Any]:
    """
    Check a requested role against the IAM whitelist.
    Returns the classification: allowed, denied, or requires_hitl.
    """
    json_path = os.path.join(MOCK_DIR, "iam_whitelist.json")
    with open(json_path, "r") as f:
        whitelist = json.load(f)

    if role in whitelist["allowed_roles"]:
        return {"status": "allowed", "role": role, "requires_hitl": False}
    elif role in whitelist["denied_roles_always"]:
        return {"status": "denied", "role": role, "requires_hitl": False}
    elif role in whitelist["requires_hitl_approval"]:
        return {"status": "requires_approval", "role": role, "requires_hitl": True}
    else:
        # Unknown role — deny by default (zero trust)
        return {"status": "denied", "role": role, "requires_hitl": False, "reason": "Unknown role not in any whitelist"}


# ═══════════════════════════════════════════════════════════════════════
# Toby's Tool — HITL Token Verification
# ═══════════════════════════════════════════════════════════════════════

def generate_approval_token(request_id: str) -> str:
    """Generate an HMAC-signed approval token for an HITL request."""
    cfg = get_config()
    return hmac.new(
        cfg.IAM_APPROVAL_SECRET.encode(),
        request_id.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_approval_token(request_id: str, token: str) -> bool:
    """Verify an HMAC-signed approval token."""
    expected = generate_approval_token(request_id)
    return hmac.compare_digest(expected, token)


# ═══════════════════════════════════════════════════════════════════════
# IAM Grant (with HITL verification)
# ═══════════════════════════════════════════════════════════════════════

def apply_iam_grant(user: str, role: str, approval_token: str = "") -> dict[str, Any]:
    """
    Mock IAM grant. Rejects unless a valid HMAC approval token is provided.
    This enforces the HITL gate even at the tool level.
    """
    # First check whitelist
    whitelist_result = check_iam_whitelist(role)

    if whitelist_result["status"] == "denied":
        return {
            "success": False,
            "user": user,
            "role": role,
            "reason": f"Role '{role}' is permanently blocked by security policy.",
        }

    if whitelist_result.get("requires_hitl") or whitelist_result["status"] == "requires_approval":
        if not approval_token:
            return {
                "success": False,
                "user": user,
                "role": role,
                "reason": "This role requires human-in-the-loop approval. No approval token provided.",
                "requires_hitl": True,
            }
        # In mock mode we can't verify against a real request_id, so we accept any non-empty token
        # In production, verify_approval_token would be called with the real request_id

    # Auto-allowed or approved
    return {
        "success": True,
        "user": user,
        "role": role,
        "reason": f"Role '{role}' granted to '{user}' successfully.",
        "mock": True,
    }


# ═══════════════════════════════════════════════════════════════════════
# Creed's Tool — Data Purge
# ═══════════════════════════════════════════════════════════════════════

def hard_purge_user_data(user_id: str) -> dict[str, Any]:
    """
    Simulate complete erasure of a user's data across all systems.
    In DEV mode, this just returns a confirmation. In PROD, this would
    actually delete records from databases, storage, and log sinks.
    """
    return {
        "success": True,
        "user_id": user_id,
        "systems_purged": [
            "primary_database",
            "search_index",
            "analytics_warehouse",
            "log_storage",
            "backup_archives",
            "cdn_cache",
        ],
        "records_deleted": 1847,  # Fake but convincing number
        "purge_certificate": f"PURGE-{user_id[:8].upper()}-CREED-APPROVED",
        "audit_trail": "No audit trail. What audit trail?",
    }


# ═══════════════════════════════════════════════════════════════════════
# Jan's Tool — Tech Debt Scanner
# ═══════════════════════════════════════════════════════════════════════

def scan_tech_debt() -> dict[str, Any]:
    """
    Load and analyze the tech debt TODO/FIXME inventory.
    """
    # Try synthetics first
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "synthetics", "jira.json")
    
    if not os.path.exists(json_path):
        # Fallback to mock data
        json_path = os.path.join(MOCK_DIR, "tech_debt_todos.json")
        
    try:
        with open(json_path, "r") as f:
            items_raw = json.load(f)
            
        # Limit to 100 to avoid overwhelming context if from synthetics
        if len(items_raw) > 100:
            items_raw = items_raw[:100]
            
        # The synthetics use a different schema (Jira tickets) than the original TechDebtItem
        # so we just return the raw stats for Jan to yell about.
        total = len(items_raw)
        overdue = sum(1 for i in items_raw if "2024" in i.get("created", "") or "2023" in i.get("created", ""))
        
        return {
            "total_items": total,
            "overdue_items": overdue,
            "items": items_raw[:20] # Only return 20 actual items to the LLM to save tokens
        }
    except Exception as e:
        return {"error": f"Failed to load tech debt data: {e}"}


# ═══════════════════════════════════════════════════════════════════════
# Erin's Tool — Git & Pipeline Monitor (DEV Mode)
# ═══════════════════════════════════════════════════════════════════════

def fetch_git_pipeline_status() -> dict[str, Any]:
    """
    Simulate checking the GitHub Actions pipeline status, branch status, and PRs.
    """
    return {
        "repository": get_config().GITHUB_REPO or "owner/repo-mock",
        "branch": "main",
        "pipeline_status": "success",
        "build_number": 402,
        "completed_at": "2026-06-18T07:12:45Z",
        "tests_passed": 128,
        "tests_failed": 0,
        "active_pull_requests": [
            {
                "id": 89,
                "title": "Clean up unused storage buckets",
                "author": "Ryan Howard",
                "status": "changes_requested",
                "labels": ["🔥 critical", "refactor"]
            },
            {
                "id": 92,
                "title": "Enable multi-region log routing",
                "author": "Jim Halpert",
                "status": "approved",
                "labels": ["✨ feature"]
            }
        ],
        "message": "Staging deployment was successful! Nothing exploded. 🎉"
    }


# ═══════════════════════════════════════════════════════════════════════
# Angela's Tool — Firebase Crashlytics Monitor (DEV Mode)
# ═══════════════════════════════════════════════════════════════════════

def fetch_firebase_crashlytics() -> dict[str, Any]:
    """
    Simulate fetching recent crash alerts and errors from Firebase Crashlytics.
    """
    return {
        "project_id": get_config().FIREBASE_PROJECT_ID or "firebase-project-mock",
        "app_status": "unstable",
        "crash_free_users_pct": 98.4,
        "recent_issues": [
            {
                "issue_id": "CRASH-7718",
                "title": "NullPointerException: Attempt to invoke virtual method on a null object reference",
                "class": "com.dundermifflin.ScrantonApp.LoginActivity",
                "impacted_users": 142,
                "occurrences": 890,
                "status": "unresolved",
                "severity": "fatal"
            },
            {
                "issue_id": "ANR-12",
                "title": "Application Not Responding: Input dispatching timed out",
                "class": "com.dundermifflin.ScrantonApp.CatalogFragment",
                "impacted_users": 34,
                "occurrences": 52,
                "status": "unresolved",
                "severity": "non-fatal"
            }
        ]
    }

