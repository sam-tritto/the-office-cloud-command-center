"""
ScrantonOS — Database Abstraction Layer
========================================
Supports CSV for DEV and Firestore for PROD.
"""

import csv
import os
import uuid
from datetime import datetime, timezone
from config import get_config

cfg = get_config()

# ── CSV Implementation (DEV) ────────────────────────────────────────

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

MESSAGES_FILE = os.path.join(DB_DIR, "messages.csv")
SESSIONS_FILE = os.path.join(DB_DIR, "sessions.csv")
AUDIT_LOG_FILE = os.path.join(DB_DIR, "audit_log.csv")

def _init_csv(file_path: str, headers: list[str]) -> None:
    if not os.path.exists(file_path):
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

if cfg.is_dev:
    _init_csv(SESSIONS_FILE, ["session_id", "created_at"])
    _init_csv(MESSAGES_FILE, ["session_id", "timestamp", "agent_id", "agent_name", "message_type", "message", "tokens_used"])
    _init_csv(AUDIT_LOG_FILE, ["timestamp", "action", "status", "details", "user", "agent"])


# ── Firestore Implementation (PROD) ─────────────────────────────────

db = None
if cfg.is_prod:
    try:
        from google.cloud import firestore
        db = firestore.Client(project=cfg.GCP_PROJECT_ID)
        print("Initialized Firestore connection.")
    except Exception as e:
        print(f"Warning: Failed to initialize Firestore: {e}")


# ── Public API ──────────────────────────────────────────────────────

def create_session() -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    if cfg.is_prod and db:
        db.collection("sessions").document(session_id).set({"created_at": now})
    else:
        with open(SESSIONS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([session_id, now])
            
    return session_id


def save_message(
    session_id: str,
    agent_id: str,
    agent_name: str,
    message_type: str,
    message: str,
    tokens_used: int = 0
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    
    if cfg.is_prod and db:
        db.collection("sessions").document(session_id).collection("messages").add({
            "timestamp": now,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "message_type": message_type,
            "message": message,
            "tokens_used": tokens_used
        })
    else:
        with open(MESSAGES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                session_id, now, agent_id, agent_name, message_type, message, tokens_used
            ])


def get_conversation_history(session_id: str, limit: int = 10) -> list[dict]:
    history = []
    
    if cfg.is_prod and db:
        messages_ref = db.collection("sessions").document(session_id).collection("messages")
        query = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        results = query.stream()
        # Firestore returns descending, we need chronological
        history = [doc.to_dict() for doc in results][::-1]
        # inject session_id to match schema
        for h in history:
            h["session_id"] = session_id
            
    else:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["session_id"] == session_id:
                        history.append(row)
            history = history[-limit:]
            
    return history


def log_audit_event(action: str, status: str, details: str, user: str = "system", agent: str = "system") -> None:
    now = datetime.now(timezone.utc).isoformat()
    
    if cfg.is_prod and db:
        db.collection("audit_log").add({
            "timestamp": now,
            "action": action,
            "status": status,
            "details": details,
            "user": user,
            "agent": agent
        })
    else:
        with open(AUDIT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([now, action, status, details, user, agent])


def get_total_tokens_used() -> int:
    total = 0
    if cfg.is_prod and db:
        # Note: Aggregation queries are expensive in Firestore for large collections.
        # A real prod app would use a counter or Cloud Functions.
        # This is simplified for the demo.
        pass
    else:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        total += int(row.get("tokens_used", 0))
                    except ValueError:
                        pass
    return total
