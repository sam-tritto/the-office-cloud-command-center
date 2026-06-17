"""
ScrantonOS — FinOps Billing Mock
================================
Provides billing metric data for cost analysis.
Now reads from generated synthetic data if available.
"""

import json
import os

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetics", "billing.json")

def compute_billing_metrics(project_id: str, days: int = 30) -> str:
    """
    Aggregates GCP billing data across major services for the specified timeframe.
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                billing = json.load(f)
                
            # Filter by last N days (mock logic just takes the whole array if it's already 30 days)
            return json.dumps(billing[-100:], indent=2) # return last 100 entries to not blow up context
        except Exception as e:
            return f"Error reading synthetics: {e}"

    # Fallback to legacy static data
    mock_data = {
        "project": project_id,
        "timeframe": f"Last {days} days",
        "total_cost": "$4,250.00",
        "services": [
            {"name": "Compute Engine", "cost": "$2,100.00", "trend": "+5%"},
            {"name": "Cloud SQL", "cost": "$1,200.00", "trend": "+2%"},
            {"name": "BigQuery", "cost": "$850.00", "trend": "+300%"},
            {"name": "Cloud Storage", "cost": "$100.00", "trend": "-1%"}
        ],
        "anomaly_detected": True,
        "anomaly_details": "BigQuery scan costs spiked 300% on 2024-03-14 due to unpartitioned queries."
    }
    return json.dumps(mock_data, indent=2)
