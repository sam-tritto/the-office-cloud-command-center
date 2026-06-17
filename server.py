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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import ScrantonWorkflow
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
