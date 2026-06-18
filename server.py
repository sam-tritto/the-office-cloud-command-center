"""
ScrantonOS — FastAPI WebSocket Server
======================================
Serves the chatbot web UI and handles real-time communication
between the browser and the ScrantonOS workflow engine.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal, Optional

from app import ScrantonWorkflow, run_agent_llm, make_agent_message
from config import get_config
from schemas.models import AgentMessage
from database import create_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scranton-server")

app = FastAPI(title="ScrantonOS", description="Dunder Mifflin Cloud Command Center")

# Serve static files from the web/ directory
WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


# ═══════════════════════════════════════════════════════════════════════
# Workflow Instance (shared across connections)
# ═══════════════════════════════════════════════════════════════════════

workflow = ScrantonWorkflow()

# Track active WebSocket connections by session_id
active_connections: dict[str, list[WebSocket]] = {}

# ── Webhook Alert → Agent Routing ──────────────────────────────────────
# Maps the alert source to the agent who should react to it.
WEBHOOK_AGENT_MAP: dict[str, str] = {
    "github": "erin",
    "logs": "dwight",
    "billing": "oscar",
    "firebase": "angela",
    "iam": "stanley",
}


async def broadcast_message(msg: AgentMessage) -> None:
    """Broadcast an agent message to connected clients for its session."""
    session_id = getattr(msg, "session_id", "default")
    if session_id not in active_connections:
        return
        
    data = msg.to_ws_json()
    disconnected = []
    for ws in active_connections[session_id]:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.append(ws)
            
    for ws in disconnected:
        active_connections[session_id].remove(ws)
    
    if not active_connections[session_id]:
        del active_connections[session_id]


async def broadcast_to_all_sessions(msg: AgentMessage) -> None:
    """Push an agent message to every active WebSocket session (for async alerts)."""
    data = msg.to_ws_json()
    dead_sessions = []
    for session_id, connections in active_connections.items():
        disconnected = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            connections.remove(ws)
        if not connections:
            dead_sessions.append(session_id)
    for s in dead_sessions:
        del active_connections[s]


# Register the broadcast callback
workflow.on_message(broadcast_message)


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@app.get("/")
async def serve_ui():
    """Serve the main chat UI."""
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await ws.accept()
    
    session_id = create_session()
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(ws)
    
    logger.info(f"Client connected. Session: {session_id}")

    # Send session initialization to client
    await ws.send_json({"type": "session_init", "session_id": session_id})

    # Send welcome message
    welcome = AgentMessage(
        session_id=session_id,
        agent_name="Michael Scott",
        agent_id="michael",
        message=(
            "Welcome to **ScrantonOS** — the Dunder Mifflin Cloud Command Center! 🏢\n\n"
            "I'm Michael Scott, World's Best Boss, and I'll be routing your requests to "
            "the finest team in Scranton. What can we help you with today?\n\n"
            "*Try commands like:*\n"
            '- "Check our cloud logs for crashes"\n'
            '- "How much are we spending on BigQuery?"\n'
            '- "Grant viewer access to alice@example.com"\n'
            '- "Scan for technical debt"\n'
            '- "Delete all data for user 12345"'
        ),
        message_type="system",
        flavor_quote="That's what she said.",
    )
    await ws.send_json(welcome.to_ws_json())

    try:
        while True:
            data = await ws.receive_text()

            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                msg = {"type": "chat", "message": data}

            msg_type = msg.get("type", "chat")
            content = msg.get("message", "")

            if msg_type == "chat" and content:
                # Echo user message back to the session
                user_msg = AgentMessage(
                    session_id=session_id,
                    agent_name="You",
                    agent_id="user",
                    message=content,
                    message_type="user_input",
                )
                await broadcast_message(user_msg)

                # Process through workflow
                try:
                    await workflow.process_input(content, session_id=session_id)
                except Exception as e:
                    logger.error(f"Workflow error: {e}", exc_info=True)
                    error_msg = AgentMessage(
                        session_id=session_id,
                        agent_name="System",
                        agent_id="system",
                        message=f"⚠️ Workflow error: {str(e)}",
                        message_type="error",
                    )
                    await broadcast_message(error_msg)

            elif msg_type == "hitl_response":
                request_id = msg.get("request_id", "")
                approved = msg.get("approved", False)
                note = msg.get("note", "")

                try:
                    await workflow.process_hitl_response(request_id, approved, note)
                except Exception as e:
                    logger.error(f"HITL error: {e}", exc_info=True)
                    error_msg = AgentMessage(
                        session_id=session_id,
                        agent_name="Toby Flenderson",
                        agent_id="toby",
                        message=f"Something went wrong with the approval process. I'm sorry. Error: {e}",
                        message_type="error",
                    )
                    await broadcast_message(error_msg)

    except WebSocketDisconnect:
        if ws in active_connections.get(session_id, []):
            active_connections[session_id].remove(ws)
        if session_id in active_connections and not active_connections[session_id]:
            del active_connections[session_id]
        logger.info(f"Client disconnected. Session: {session_id}")


# ═══════════════════════════════════════════════════════════════════════
# Webhook Alert Ingestion Endpoint
# ═══════════════════════════════════════════════════════════════════════

class AlertPayload(BaseModel):
    """Schema for inbound webhook alerts from external systems."""
    source: Literal["github", "logs", "billing", "firebase", "iam"] = "github"
    event: str  # e.g. 'failure', 'success', 'anomaly', 'critical'
    repository: Optional[str] = None
    message: Optional[str] = None
    severity: Optional[str] = None


@app.post("/api/webhooks/alerts")
async def ingest_alert(payload: AlertPayload):
    """
    Receive an external alert event and dispatch an async in-character
    notification to all connected WebSocket clients.

    Example curl:
        curl -X POST http://localhost:8000/api/webhooks/alerts \\
          -H 'Content-Type: application/json' \\
          -d '{"source": "github", "event": "failure", "repository": "scranton-os", "message": "Tests failed on main"}'
    """
    agent_id = WEBHOOK_AGENT_MAP.get(payload.source, "michael")

    # Build a rich context prompt for the agent
    context_parts = [f"An external alert has arrived from the {payload.source.upper()} system."]
    context_parts.append(f"Event type: {payload.event}")
    if payload.repository:
        context_parts.append(f"Repository: {payload.repository}")
    if payload.message:
        context_parts.append(f"Details: {payload.message}")
    if payload.severity:
        context_parts.append(f"Severity: {payload.severity}")
    context_parts.append(
        "React to this alert in character. Be concise (2-4 sentences). "
        "Do NOT ask clarifying questions — just report and react."
    )
    prompt = "\n".join(context_parts)

    logger.info(f"Webhook alert received: source={payload.source} event={payload.event}")

    if not active_connections:
        logger.info("No active sessions to notify.")
        return {"status": "no_active_sessions", "agent": agent_id}

    # Generate in-character response (uses mock response if no API key)
    try:
        response_text = await run_agent_llm(agent_id, prompt, session_id="webhook")
    except Exception as e:
        logger.error(f"Agent LLM failed for webhook alert: {e}")
        response_text = f"Alert received from {payload.source}: {payload.message or payload.event}"

    # Build the agent message with webhook_alert type
    msg = make_agent_message(
        agent_id,
        response_text,
        message_type="webhook_alert",
        metadata={
            "source": payload.source,
            "event": payload.event,
            "repository": payload.repository,
            "severity": payload.severity,
        },
        session_id="webhook",
    )

    await broadcast_to_all_sessions(msg)
    return {"status": "ok", "agent": agent_id, "sessions_notified": len(active_connections)}


# ═══════════════════════════════════════════════════════════════════════
# HITL REST Endpoint (alternative to WebSocket)
# ═══════════════════════════════════════════════════════════════════════

class HITLApprovalRequest(BaseModel):
    request_id: str
    approved: bool
    note: str = ""


@app.post("/hitl/approve")
async def hitl_approve(req: HITLApprovalRequest):
    """REST endpoint for HITL approval/rejection."""
    messages = await workflow.process_hitl_response(req.request_id, req.approved, req.note)
    return {"status": "ok", "messages": [m.to_ws_json() for m in messages]}


# ═══════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    cfg = get_config()
    return {
        "status": "ok",
        "env": cfg.ENV,
        "api_key_configured": bool(cfg.GEMINI_API_KEY),
        "active_connections": len(active_connections),
        "pending_hitl": len(workflow.pending_hitl),
    }


# ═══════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    cfg = get_config()
    print("=" * 60)
    print("  🏢 ScrantonOS Server")
    print("=" * 60)
    print(f"  Environment: {cfg.ENV}")
    print(f"  API Key: {'✅' if cfg.GEMINI_API_KEY else '⚠️  not set'}")
    print(f"  URL: http://{cfg.HOST}:{cfg.PORT}")
    print("=" * 60)

    uvicorn.run(
        "server:app",
        host=cfg.HOST,
        port=cfg.PORT,
        reload=True,
        log_level="info",
    )
