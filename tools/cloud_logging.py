"""
ScrantonOS — Cloud Logging Tool
===============================
Provides deterministic mock logs for testing agent analysis patterns.
Now reads from generated synthetic data if available.
"""

import json
import os
from typing import Optional

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetics", "logs.json")

def fetch_app_logs(service_name: str, lookback_minutes: int = 60) -> str:
    """
    Fetches the most recent logs for a specific service.
    
    Args:
        service_name: The name of the GCP service (e.g., payment-gateway)
        lookback_minutes: How many minutes back to query
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
            
            # Filter by service
            filtered_logs = [
                log for log in logs 
                if log.get("resource", {}).get("labels", {}).get("container_name") == service_name
            ]
            
            # For the mock, just return the last 10 logs of that service
            return json.dumps(filtered_logs[-10:], indent=2)
        except Exception as e:
            return f"Error reading synthetics: {e}"
            
    # Fallback to legacy static data if synthetics haven't been generated
    mock_data = [
        {
            "insertId": "1a2b3c",
            "timestamp": "2024-03-15T10:00:00Z",
            "severity": "INFO",
            "textPayload": f"Service {service_name} started successfully"
        },
        {
            "insertId": "1a2b3d",
            "timestamp": "2024-03-15T10:05:12Z",
            "severity": "ERROR",
            "textPayload": "Connection timeout to primary database cluster"
        },
        {
            "insertId": "1a2b3e",
            "timestamp": "2024-03-15T10:05:15Z",
            "severity": "CRITICAL",
            "textPayload": "Pod restarted due to OOMKilled"
        }
    ]
    return json.dumps(mock_data, indent=2)


def analyze_logs_structured(log_json: str) -> str:
    """
    A helper tool that takes a raw JSON log dump and returns a parsed summary.
    """
    try:
        data = json.loads(log_json)
        error_count = sum(1 for item in data if item.get("severity") in ("ERROR", "CRITICAL"))
        return f"Found {len(data)} total log entries. {error_count} are severe."
    except Exception:
        return "Failed to parse log JSON."
