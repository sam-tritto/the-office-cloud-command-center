"""
ScrantonOS — Synthetic Data Generator
======================================
Generates thousands of realistic JSON records for logs, billing, and tech debt
to simulate a real cloud environment for the agents to analyze.
"""

import json
import os
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetics")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
BILLING_FILE = os.path.join(DATA_DIR, "billing.json")
JIRA_FILE = os.path.join(DATA_DIR, "jira.json")


def generate_logs(count: int = 5000):
    """Generate GCP-style structured logs with occasional anomalies."""
    print(f"Generating {count} synthetic log entries...")
    logs = []
    
    services = ["user-auth-service", "payment-gateway", "inventory-api", "frontend-node"]
    
    # Create an anomaly window yesterday
    anomaly_time = datetime.utcnow() - timedelta(days=1)
    
    for i in range(count):
        # Distribute logs over the last 7 days
        timestamp = fake.date_time_between(start_date="-7d", end_date="now")
        service = random.choice(services)
        
        # Determine severity
        if random.random() < 0.05:
            severity = "ERROR"
            message = fake.sentence(nb_words=6) + " (Failed)"
        elif random.random() < 0.15:
            severity = "WARNING"
            message = f"Latency spike: {random.randint(500, 2000)}ms"
        else:
            severity = "INFO"
            message = f"Request processed successfully: {fake.uuid4()}"
            
        # Inject an anomaly for Dwight to find
        if anomaly_time <= timestamp <= anomaly_time + timedelta(minutes=10) and service == "payment-gateway":
            severity = "CRITICAL"
            message = "FATAL: Connection pool exhausted to primary database instance pg-cluster-1"

        logs.append({
            "insertId": fake.uuid4(),
            "timestamp": timestamp.isoformat() + "Z",
            "severity": severity,
            "resource": {
                "type": "k8s_container",
                "labels": {
                    "cluster_name": "prod-cluster",
                    "namespace_name": "default",
                    "container_name": service
                }
            },
            "textPayload": message
        })
        
    # Sort by timestamp
    logs.sort(key=lambda x: x["timestamp"])
    
    with open(LOGS_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)


def generate_billing(days: int = 30):
    """Generate daily billing data with one major anomaly."""
    print(f"Generating {days} days of synthetic billing data...")
    billing = []
    
    services = ["Compute Engine", "Cloud SQL", "Cloud Storage", "BigQuery"]
    base_costs = {
        "Compute Engine": 150.00,
        "Cloud SQL": 80.00,
        "Cloud Storage": 20.00,
        "BigQuery": 40.00
    }
    
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=days - i)).strftime("%Y-%m-%d")
        
        for service in services:
            cost = base_costs[service] * random.uniform(0.9, 1.1)
            
            # Inject anomaly 5 days ago in BigQuery
            if i == days - 5 and service == "BigQuery":
                cost = base_costs[service] * 8.5  # 850% spike
                
            billing.append({
                "date": date,
                "service": service,
                "cost": round(cost, 2),
                "currency": "USD"
            })
            
    with open(BILLING_FILE, "w", encoding="utf-8") as f:
        json.dump(billing, f, indent=2)


def generate_jira_tickets(count: int = 500):
    """Generate tech debt tickets with varying ages."""
    print(f"Generating {count} synthetic tech debt tickets...")
    tickets = []
    
    status_options = ["Open", "In Progress", "Backlog"]
    
    for i in range(count):
        # Generate some very old tickets for Jan
        if random.random() < 0.1:
            created = fake.date_time_between(start_date="-800d", end_date="-400d")
        else:
            created = fake.date_time_between(start_date="-100d", end_date="now")
            
        tickets.append({
            "key": f"TECH-{fake.random_int(min=1000, max=9999)}",
            "summary": fake.sentence(nb_words=8),
            "description": fake.paragraph(nb_sentences=3),
            "status": random.choice(status_options),
            "created": created.strftime("%Y-%m-%d"),
            "assignee": fake.name() if random.random() < 0.7 else "Unassigned",
            "component": random.choice(["Frontend", "Backend", "Database", "Infrastructure"])
        })
        
    with open(JIRA_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2)


if __name__ == "__main__":
    print("=" * 50)
    print("Starting Synthetic Data Generation")
    print("=" * 50)
    generate_logs()
    generate_billing()
    generate_jira_tickets()
    print("=" * 50)
    print(f"Synthetics saved to {DATA_DIR}")
    print("=" * 50)
