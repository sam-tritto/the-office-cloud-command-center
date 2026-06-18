"""
ScrantonOS — Main Application Workflow
========================================
The core orchestration engine that wires all character agents into a
directed workflow. Processes user input through Michael (orchestrator),
routes to specialist agents, and handles the HITL approval gate.

This module can run standalone for CLI testing or be imported by
server.py for the WebSocket-based chatbot UI.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from config import get_config
from schemas.models import (
    AgentMessage,
    CommandIntent,
    HITLPayload,
    HITLResponse,
    IAMRequest,
    IAMVerdict,
    UserCommand,
)
from tools import (
    analyze_logs_structured,
    apply_iam_grant,
    check_iam_whitelist,
    compute_billing_metrics,
    fetch_app_logs,
    generate_approval_token,
    hard_purge_user_data,
    query_billing_data,
    scan_tech_debt,
    verify_approval_token,
    fetch_git_pipeline_status,
    fetch_firebase_crashlytics,
)
from database import save_message, get_conversation_history, log_audit_event, get_total_tokens_used

# Agent instructions
from agents.michael import MICHAEL_INSTRUCTION
from agents.dwight import DWIGHT_INSTRUCTION
from agents.oscar import OSCAR_INSTRUCTION
from agents.stanley import STANLEY_INSTRUCTION
from agents.toby import TOBY_INSTRUCTION
from agents.angela import ANGELA_INSTRUCTION
from agents.jim import JIM_INSTRUCTION
from agents.meredith import MEREDITH_INSTRUCTION
from agents.gabe import GABE_INSTRUCTION
from agents.jan import JAN_INSTRUCTION
from agents.bob_vance import BOB_VANCE_INSTRUCTION
from agents.creed import CREED_INSTRUCTION
from agents.pam import PAM_INSTRUCTION
from agents.erin import ERIN_INSTRUCTION
from agents.kevin import KEVIN_INSTRUCTION
from agents.ryan import RYAN_INSTRUCTION

from agents import get_random_quote, CHARACTER_COLORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scranton-os")


# ═══════════════════════════════════════════════════════════════════════
# Intent → Agent Routing Map
# ═══════════════════════════════════════════════════════════════════════

INTENT_AGENT_MAP: dict[CommandIntent, str] = {
    CommandIntent.SRE: "dwight",
    CommandIntent.FINOPS: "oscar",
    CommandIntent.FIREBASE: "angela",
    CommandIntent.IAM: "stanley",
    CommandIntent.TECH_DEBT: "jan",
    CommandIntent.UI_REVIEW: "jim",
    CommandIntent.CHAOS_TEST: "meredith",
    CommandIntent.DOCS: "gabe",
    CommandIntent.LEGACY: "bob_vance",
    CommandIntent.PURGE: "creed",
    CommandIntent.REPORT: "pam",
    CommandIntent.GIT_OPS: "erin",
    CommandIntent.METRICS: "kevin",
    CommandIntent.MODERNIZE: "ryan",
    CommandIntent.GENERAL: "michael",
}

AGENT_INSTRUCTIONS: dict[str, str] = {
    "michael": MICHAEL_INSTRUCTION,
    "dwight": DWIGHT_INSTRUCTION,
    "oscar": OSCAR_INSTRUCTION,
    "stanley": STANLEY_INSTRUCTION,
    "toby": TOBY_INSTRUCTION,
    "angela": ANGELA_INSTRUCTION,
    "jim": JIM_INSTRUCTION,
    "meredith": MEREDITH_INSTRUCTION,
    "gabe": GABE_INSTRUCTION,
    "jan": JAN_INSTRUCTION,
    "bob_vance": BOB_VANCE_INSTRUCTION,
    "creed": CREED_INSTRUCTION,
    "pam": PAM_INSTRUCTION,
    "erin": ERIN_INSTRUCTION,
    "kevin": KEVIN_INSTRUCTION,
    "ryan": RYAN_INSTRUCTION,
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "michael": "Michael Scott",
    "dwight": "Dwight Schrute",
    "oscar": "Oscar Martinez",
    "stanley": "Stanley Hudson",
    "toby": "Toby Flenderson",
    "angela": "Angela Martin",
    "jim": "Jim Halpert",
    "meredith": "Meredith Palmer",
    "gabe": "Gabe Lewis",
    "jan": "Jan Levinson",
    "bob_vance": "Bob Vance",
    "creed": "Creed Bratton",
    "pam": "Pam Beesly",
    "erin": "Erin Hannon",
    "kevin": "Kevin Malone",
    "ryan": "Ryan Howard",
}


# ═══════════════════════════════════════════════════════════════════════
# Intent Classification (Deterministic Keyword-Based)
# ═══════════════════════════════════════════════════════════════════════

# Keyword → intent mapping for fast, deterministic classification
# The LLM (Michael) provides personality; routing is code-based for security
INTENT_KEYWORDS: dict[CommandIntent, list[str]] = {
    CommandIntent.SRE: [
        "logs", "crash", "error", "memory", "leak", "oom", "container",
        "failure", "uptime", "incident", "outage", "alert", "monitor",
        "sre", "reliability", "health check", "status", "down", "502", "504",
        "timeout", "latency", "performance", "system",
    ],
    CommandIntent.FINOPS: [
        "billing", "cost", "spend", "budget", "expense", "invoice",
        "finops", "price", "charge", "bigquery cost", "gpu cost",
        "compute cost", "storage cost", "burn rate", "savings",
        "over budget", "cloud spend", "money",
    ],
    CommandIntent.FIREBASE: [
        "firebase", "crashlytics", "anr", "mobile crash", "app crash",
        "firebase config", "fcm", "firestore", "realtime database",
    ],
    CommandIntent.IAM: [
        "iam", "access", "permission", "role", "grant", "revoke",
        "policy", "service account", "credentials", "authenticate",
        "authorize", "security", "admin access", "viewer access",
    ],
    CommandIntent.TECH_DEBT: [
        "todo", "fixme", "hack", "technical debt", "tech debt",
        "backlog", "sprint", "velocity", "overdue", "ticket",
        "code quality", "cleanup", "refactor",
    ],
    CommandIntent.UI_REVIEW: [
        "ui", "ux", "frontend", "front-end", "css", "layout",
        "design", "component", "styling", "pixel", "alignment",
        "responsive", "accessibility", "a11y", "visual",
    ],
    CommandIntent.CHAOS_TEST: [
        "chaos", "fuzz", "stress test", "load test", "rate limit",
        "ddos", "benchmark", "performance test", "breaking point",
        "resilience", "fault injection",
    ],
    CommandIntent.DOCS: [
        "documentation", "docs", "wiki", "how to", "how do",
        "guide", "manual", "procedure", "protocol", "onboarding",
        "reference", "section",
    ],
    CommandIntent.LEGACY: [
        "legacy", "migration", "archive", "cold storage", "glacier",
        "old system", "mainframe", "on-premise", "on-prem",
        "migrate", "backup", "archival",
    ],
    CommandIntent.PURGE: [
        "delete", "purge", "erase", "gdpr", "right to be forgotten",
        "pii", "remove user", "data deletion", "scrub", "wipe",
        "forget", "destroy",
    ],
    CommandIntent.REPORT: [
        "report", "summary", "artifact", "document", "format",
        "generate report", "create report", "executive summary",
    ],
    CommandIntent.GIT_OPS: [
        "git", "deploy", "deployment", "ci/cd", "pipeline",
        "build", "merge", "branch", "pr", "pull request",
        "commit", "release", "rollback",
    ],
    CommandIntent.METRICS: [
        "dashboard", "metrics", "count", "calculate", "math",
        "how many", "total", "sum", "average", "stats",
    ],
    CommandIntent.MODERNIZE: [
        "modernize", "rewrite", "scale", "architecture", "rust",
        "web3", "ai", "serverless", "go", "golang", "microservices",
        "wuphf",
    ],
}


def classify_intent(user_input: str) -> CommandIntent:
    """
    Deterministic intent classification based on keyword matching.
    This runs BEFORE the LLM to ensure routing cannot be manipulated
    via prompt injection (key security guardrail).
    """
    input_lower = user_input.lower()
    scores: dict[CommandIntent, int] = {}

    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in input_lower)
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)

    return CommandIntent.GENERAL


# ═══════════════════════════════════════════════════════════════════════
# Agent Message Factory
# ═══════════════════════════════════════════════════════════════════════

def make_agent_message(
    agent_id: str,
    message: str,
    message_type: str = "agent_response",
    metadata: Optional[dict] = None,
    session_id: str = "default",
) -> AgentMessage:
    """Create an AgentMessage with a random flavor quote."""
    return AgentMessage(
        session_id=session_id,
        agent_name=AGENT_DISPLAY_NAMES.get(agent_id, agent_id),
        agent_id=agent_id,
        message=message,
        message_type=message_type,
        flavor_quote=get_random_quote(agent_id),
        timestamp=datetime.now(timezone.utc),
        metadata=metadata or {},
    )


# ═══════════════════════════════════════════════════════════════════════
# LLM Agent Runner (Antigravity SDK Integration)
# ═══════════════════════════════════════════════════════════════════════

async def run_agent_llm(
    agent_id: str,
    prompt: str,
    session_id: str = "default",
    api_key: str = "",
) -> str:
    """
    Run an LLM agent using the Google Antigravity SDK.
    Falls back to a mock response if no API key is available.
    """
    cfg = get_config()
    api_key = api_key or cfg.GEMINI_API_KEY
    
    # Token Budget Enforcement
    total_tokens = get_total_tokens_used()
    if total_tokens >= cfg.MAX_TOKEN_BUDGET:
        msg = f"ERROR: Maximum token budget of {cfg.MAX_TOKEN_BUDGET} exceeded. Operations halted."
        logger.error(msg)
        return msg

    # Conversation Memory Injection
    history = get_conversation_history(session_id, limit=8)
    history_text = "\n".join([f"{r['agent_name']} ({r['message_type']}): {r['message']}" for r in history])
    
    full_prompt = prompt
    if history_text:
        full_prompt = f"Previous conversation history:\n{history_text}\n\nCurrent Request:\n{prompt}"

    if not api_key:
        # No API key — generate a mock response using the character persona
        logger.warning(f"No GEMINI_API_KEY — using mock response for {agent_id}")
        resp = _generate_mock_response(agent_id, full_prompt)
        tokens = len(full_prompt.split()) + len(resp.split())
        save_message(session_id, agent_id, AGENT_DISPLAY_NAMES.get(agent_id, agent_id), "agent_response", resp, tokens)
        return resp

    try:
        from google.antigravity import Agent, LocalAgentConfig

        instruction = AGENT_INSTRUCTIONS.get(agent_id, "You are a helpful assistant.")

        config = LocalAgentConfig(
            api_key=api_key,
            system_instructions=instruction,
        )

        async with Agent(config) as agent:
            response = await agent.chat(full_prompt)
            resp_text = await response.text()
            tokens = len(full_prompt.split()) + len(resp_text.split())
            save_message(session_id, agent_id, AGENT_DISPLAY_NAMES.get(agent_id, agent_id), "agent_response", resp_text, tokens)
            return resp_text

    except ImportError:
        logger.warning("google-antigravity not installed — using mock response")
        resp = _generate_mock_response(agent_id, full_prompt)
        tokens = len(full_prompt.split()) + len(resp.split())
        save_message(session_id, agent_id, AGENT_DISPLAY_NAMES.get(agent_id, agent_id), "agent_response", resp, tokens)
        return resp
    except Exception as e:
        logger.error(f"Agent {agent_id} failed: {e}")
        resp = _generate_mock_response(agent_id, full_prompt)
        tokens = len(full_prompt.split()) + len(resp.split())
        save_message(session_id, agent_id, AGENT_DISPLAY_NAMES.get(agent_id, agent_id), "agent_response", resp, tokens)
        return resp


def _generate_mock_response(agent_id: str, prompt: str) -> str:
    """Generate a character-appropriate mock response when LLM is unavailable."""
    quote = get_random_quote(agent_id)
    name = AGENT_DISPLAY_NAMES.get(agent_id, agent_id)

    mock_responses: dict[str, str] = {
        "michael": f"Alright everybody, listen up! I've reviewed the situation and here's what we're going to do. I'm routing this to the best person on my team. That's what a World's Best Boss does. *{quote}*",
        "dwight": f"THREAT DETECTED. I've analyzed the data and the situation is SERIOUS. As Assistant Regional Manager, I am declaring Threat Level: ORANGE. The system has vulnerabilities that I, and only I, can properly assess. Full analysis follows.\n\n*{quote}*",
        "oscar": f"Actually... let me look at these numbers properly. The data suggests some concerning trends that I think everyone is overlooking. Let me break this down in a way that even Michael could understand.\n\n*{quote}*",
        "stanley": f"No. I've reviewed the request. My verdict stands. Don't ask me again.\n\n*{quote}*",
        "toby": f"I'm sorry, but I need to pause this workflow for review. I know nobody likes this part, but compliance requires it. Please review the details below and either approve or reject.\n\n*{quote}*",
        "angela": f"This is unacceptable. I've reviewed the data and it does not meet my standards. Not even close. I have a list of issues and you will address every single one.\n\n*{quote}*",
        "jim": f"So I took a look at this and... yeah. It's fine. I mean, it's not great. The alignment is off and there are some choices being made here that I'd call 'bold.' But it works. Mostly.\n\n*{quote}*",
        "meredith": f"I hit the endpoint as hard as I could. Some things broke. Some things survived. You're welcome for finding out which is which before your users did.\n\n*{quote}*",
        "gabe": f"Per the internal documentation, Section 4, Subsection B, I've located the relevant procedures. Please review the following excerpts carefully.\n\n*{quote}*",
        "jan": f"I've audited the backlog and the results are UNACCEPTABLE. We are freezing all feature work until this technical debt is resolved. No exceptions. Effective immediately.\n\n*{quote}*",
        "bob_vance": f"Bob Vance, Vance Code Migration. I've reviewed the legacy data and I'll have it packed up tight and moved to cold storage. Solid as a commercial freezer.\n\n*{quote}*",
        "creed": f"Done. What records? I don't know what you're talking about. Those never existed. Nobody saw anything.\n\n*{quote}*",
        "pam": f"I've put together a clean report with proper formatting, headers, and even some color-coding. I hope it helps! I put a lot of thought into the layout.\n\n*{quote}*",
        "erin": f"Oh my gosh! I checked the pipeline and everything is looking GREAT! Well, mostly great. There's one tiny thing but I'm sure it's fine! 🎉\n\n*{quote}*",
    }

    return mock_responses.get(agent_id, f"[{name}]: Processing your request... *{quote}*")


# ═══════════════════════════════════════════════════════════════════════
# Workflow Engine
# ═══════════════════════════════════════════════════════════════════════

class ScrantonWorkflow:
    """
    The main ScrantonOS workflow engine. Processes user input through
    the character agent pipeline and manages HITL approval gates.
    """

    def __init__(self):
        self.config = get_config()
        self.pending_hitl: dict[str, HITLPayload] = {}
        self._message_callback: Optional[Callable] = None

    def on_message(self, callback: Callable[[AgentMessage], Any]) -> None:
        """Register a callback for when agents produce messages."""
        self._message_callback = callback

    async def _emit(self, msg: AgentMessage) -> None:
        """Emit an agent message to the registered callback."""
        if self._message_callback:
            await self._message_callback(msg)
        else:
            # CLI fallback — just print
            print(f"\n[{msg.agent_name}]: {msg.message}")
            if msg.flavor_quote:
                print(f'  💬 "{msg.flavor_quote}"')

    async def process_input(self, user_input: str, session_id: str = "default") -> list[AgentMessage]:
        """
        Main entry point. Process a user's natural language input
        through the entire ScrantonOS pipeline.

        Returns a list of all AgentMessages produced during processing.
        """
        messages: list[AgentMessage] = []

        async def collect_and_emit(msg: AgentMessage):
            messages.append(msg)
            await self._emit(msg)

        # Save original callback, use collector
        original_cb = self._message_callback
        self._message_callback = collect_and_emit if not original_cb else \
            lambda msg: _dual_emit(msg, original_cb, messages)

        try:
            # Save user input to memory
            save_message(session_id, "user", "You", "user_input", user_input, len(user_input.split()))
            
            # Step 1: Classify intent (deterministic — cannot be prompt-injected)
            intent = classify_intent(user_input)
            logger.info(f"Classified intent: {intent.value}")

            # Step 2: Michael acknowledges and routes
            michael_prompt = (
                f"A user has sent the following request to ScrantonOS:\n\n"
                f'"{user_input}"\n\n'
                f"The system has classified this as: {intent.value}\n"
                f"Route this to the appropriate team member and introduce them."
            )
            michael_response = await run_agent_llm("michael", michael_prompt, session_id)
            await collect_and_emit(make_agent_message("michael", michael_response, session_id=session_id))

            # Step 3: Central Michael-Controlled Loop for Multi-Agent Chains
            current_intent = intent
            current_input = user_input
            
            loop_count = 0
            while loop_count < 3:
                target_agent = INTENT_AGENT_MAP.get(current_intent, "michael")

                if target_agent == "michael":
                    break
                else:
                    specialist_response = await self._run_specialist(target_agent, current_intent, current_input, collect_and_emit, session_id)
                    
                    # Agent Banter
                    if random.random() < 0.15:
                        rivals = [k for k in AGENT_DISPLAY_NAMES.keys() if k not in (target_agent, "user", "system", "michael")]
                        if rivals:
                            rival = random.choice(rivals)
                            banter_prompt = f"{AGENT_DISPLAY_NAMES[target_agent]} just handled a task and said: '{specialist_response}'. Provide a short, in-character reaction, comment, or mild insult."
                            banter_resp = await run_agent_llm(rival, banter_prompt, session_id)
                            await collect_and_emit(make_agent_message(rival, banter_resp, session_id=session_id))

                    # Michael Evaluation
                    eval_prompt = (
                        f"The specialist {AGENT_DISPLAY_NAMES[target_agent]} just handled the task and responded with:\n{specialist_response}\n\n"
                        f"Does this require another specialist to follow up? (e.g. if an error was found, maybe we need the 'report' intent or 'git_ops'). "
                        f"If so, reply with ONLY the exact intent name from this list: {', '.join([i.value for i in CommandIntent])}. "
                        f"If no further action is needed, reply with 'DONE'."
                    )
                    eval_response = await run_agent_llm("michael", eval_prompt, session_id)
                    clean_eval = eval_response.strip().lower()
                    
                    if clean_eval in [i.value for i in CommandIntent]:
                        current_intent = CommandIntent(clean_eval)
                        current_input = f"Follow up on the previous finding: {specialist_response}"
                        
                        # Michael announces the handoff
                        handoff_resp = await run_agent_llm("michael", f"Announce that you are now handing this off to the team member responsible for {clean_eval}.", session_id)
                        await collect_and_emit(make_agent_message("michael", handoff_resp, session_id=session_id))
                        loop_count += 1
                    else:
                        break

        finally:
            self._message_callback = original_cb

        return messages

    async def _run_specialist(
        self,
        agent_id: str,
        intent: CommandIntent,
        user_input: str,
        emit: Callable,
        session_id: str = "default",
    ) -> str:
        """Run a specialist agent with its relevant tools and context."""
        response_text = ""

        if intent == CommandIntent.SRE:
            response_text = await self._run_sre(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.FINOPS:
            response_text = await self._run_finops(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.IAM:
            response_text = await self._run_iam(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.TECH_DEBT:
            response_text = await self._run_tech_debt(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.PURGE:
            response_text = await self._run_purge(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.GIT_OPS:
            response_text = await self._run_git_ops(agent_id, user_input, emit, session_id)
        elif intent == CommandIntent.FIREBASE:
            response_text = await self._run_firebase(agent_id, user_input, emit, session_id)
        else:
            # Generic specialist — just pass the prompt through
            prompt = f"User request: {user_input}\n\nProvide your expert analysis."
            response_text = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response_text, session_id=session_id))
            
        return response_text

    async def _run_sre(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Dwight analyzes logs."""
        try:
            logs = fetch_app_logs()
            metrics = analyze_logs_structured(logs)

            prompt = (
                f"User request: {user_input}\n\n"
                f"Here is the log data from our systems:\n"
                f"```json\n{json.dumps(metrics, indent=2)}\n```\n\n"
                f"Sample log entries (first 10):\n"
                f"```json\n{json.dumps(logs[:10], indent=2)}\n```\n\n"
                f"Analyze these logs and provide your threat assessment."
            )
            response = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response, session_id=session_id))
            return response

        except Exception as e:
            error_resp = f"CRITICAL FAILURE: Unable to access log systems. The threat is INSIDE the monitoring infrastructure. Error: {e}"
            await emit(make_agent_message(agent_id, error_resp, message_type="error", session_id=session_id))
            return error_resp

    async def _run_finops(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Oscar analyzes billing data."""
        try:
            raw_data = query_billing_data()
            metrics = compute_billing_metrics(raw_data)

            prompt = (
                f"User request: {user_input}\n\n"
                f"Here is the billing analysis for the current period:\n"
                f"```json\n{json.dumps(metrics, indent=2)}\n```\n\n"
                f"Provide your detailed financial analysis."
            )
            response = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response, session_id=session_id))
            return response

        except Exception as e:
            error_resp = f"Actually... I can't access the billing data right now. And that is concerning. Error: {e}"
            await emit(make_agent_message(agent_id, error_resp, message_type="error", session_id=session_id))
            return error_resp

    async def _run_iam(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Stanley checks IAM, potentially routes through Toby HITL gate."""
        input_lower = user_input.lower()
        target_role = self._extract_role(input_lower)
        target_user = self._extract_email(user_input)

        if not target_role:
            resp = "You need to specify a role. I'm not a mind reader. And even if I were, I still wouldn't care enough to read yours."
            await emit(make_agent_message("stanley", resp, session_id=session_id))
            return resp

        whitelist_result = check_iam_whitelist(target_role)

        if whitelist_result["status"] == "denied":
            prompt = (
                f"An IAM access request has been made:\n"
                f"- User: {target_user or 'not specified'}\n"
                f"- Role: {target_role}\n"
                f"- Whitelist result: DENIED\n"
                f"- Reason: This role is on the permanently blocked list.\n\n"
                f"Deliver your verdict."
            )
            response = await run_agent_llm("stanley", prompt, session_id)
            log_audit_event("IAM_GRANT", "DENIED", f"Role {target_role} blocked by whitelist", target_user or "unknown", "stanley")
            await emit(make_agent_message("stanley", response, session_id=session_id))
            return response

        elif whitelist_result["status"] == "allowed":
            prompt = (
                f"An IAM access request has been made:\n"
                f"- User: {target_user or 'not specified'}\n"
                f"- Role: {target_role}\n"
                f"- Whitelist result: APPROVED (auto-allowed viewer role)\n\n"
                f"Deliver your verdict."
            )
            response = await run_agent_llm("stanley", prompt, session_id)
            await emit(make_agent_message("stanley", response, session_id=session_id))

            result = apply_iam_grant(target_user or "unknown", target_role)
            log_audit_event("IAM_GRANT", "APPROVED_AUTO", f"Role {target_role} auto-granted", target_user or "unknown", "stanley")
            if result["success"]:
                sys_msg = f"✅ Role `{target_role}` granted to `{target_user}`. Done. Can I go home now?"
                await emit(make_agent_message("stanley", sys_msg, message_type="system", session_id=session_id))
                return f"{response}\n\n{sys_msg}"
            return response

        elif whitelist_result.get("requires_hitl"):
            resp = f"This role (`{target_role}`) requires human approval. Routing to HR. Unfortunately."
            await emit(make_agent_message("stanley", resp, session_id=session_id))
            await self._hitl_gate(target_user or "unknown", target_role, user_input, emit, session_id)
            return resp
        
        return "Processed IAM request."

    async def _hitl_gate(
        self,
        target_user: str,
        target_role: str,
        user_input: str,
        emit: Callable,
        session_id: str,
    ) -> None:
        """Toby's HITL approval gate — pauses workflow for human review."""
        request_id = str(uuid.uuid4())
        approval_token = generate_approval_token(request_id)

        payload = HITLPayload(
            request_id=request_id,
            action_type="iam_grant",
            action_details={
                "target_user": target_user,
                "target_role": target_role,
                "original_request": user_input,
                "session_id": session_id,
            },
            requesting_agent="stanley",
            risk_level="high",
            toby_message=(
                f"I'm sorry to interrupt, but this IAM grant requires human approval. "
                f"User `{target_user}` is requesting `{target_role}`. "
                f"I know this is annoying, but... it's my job."
            ),
        )

        self.pending_hitl[request_id] = payload

        # Emit Toby's message with HITL payload
        toby_prompt = (
            f"A privileged IAM action requires your approval:\n"
            f"- User: {target_user}\n"
            f"- Role: {target_role}\n"
            f"- Risk Level: HIGH\n\n"
            f"Present this for human review."
        )
        response = await run_agent_llm("toby", toby_prompt, session_id)
        log_audit_event("HITL_REQUESTED", "PENDING", f"Approval requested for {target_role}", target_user, "toby")
        await emit(make_agent_message(
            "toby",
            response,
            message_type="hitl_pause",
            metadata=payload.model_dump(mode="json"),
            session_id=session_id,
        ))

    async def process_hitl_response(self, request_id: str, approved: bool, note: str = "") -> list[AgentMessage]:
        """Process a human's HITL approval/rejection response."""
        messages: list[AgentMessage] = []
        
        payload = self.pending_hitl.pop(request_id, None)
        session_id = payload.action_details.get("session_id", "default") if payload else "default"

        async def collect(msg: AgentMessage):
            messages.append(msg)
            if self._message_callback:
                await self._message_callback(msg)

        if not payload:
            await collect(make_agent_message(
                "toby",
                f"I... don't have a record of that request. This is awkward. Request ID: {request_id}",
                message_type="error",
                session_id=session_id,
            ))
            return messages

        details = payload.action_details

        if approved:
            approval_token = generate_approval_token(request_id)
            target_role = details.get("target_role", "unknown")
            target_user = details.get("target_user", "unknown")
            result = apply_iam_grant(target_user, target_role, approval_token)

            log_audit_event("HITL_RESOLVED", "APPROVED", f"Approved by human: {note}", target_user, "human")
            await collect(make_agent_message(
                "toby",
                f"✅ Approved! The IAM grant has been executed. Thank you for your patience with the process.",
                message_type="hitl_resume",
                session_id=session_id,
            ))

            if result["success"]:
                await collect(make_agent_message(
                    "stanley",
                    f"Fine. `{target_role}` granted to `{target_user}`. "
                    f"Approved by human operator. Are we done here?",
                    message_type="system",
                    session_id=session_id,
                ))
        else:
            log_audit_event("HITL_RESOLVED", "REJECTED", f"Rejected by human: {note}", details.get("target_user", "unknown"), "human")
            await collect(make_agent_message(
                "toby",
                f"❌ Rejected. The IAM grant has been denied by the human operator. "
                f"Note: {note or 'No reason provided.'}",
                message_type="hitl_resume",
                session_id=session_id,
            ))
            await collect(make_agent_message(
                "stanley",
                "Good. I didn't want to approve it anyway.",
                message_type="system",
                session_id=session_id,
            ))

        return messages

    async def _run_tech_debt(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Jan audits technical debt."""
        try:
            debt_data = scan_tech_debt()

            prompt = (
                f"User request: {user_input}\n\n"
                f"Here is the technical debt inventory:\n"
                f"```json\n{json.dumps(debt_data, indent=2)}\n```\n\n"
                f"Provide your executive assessment of the engineering debt situation."
            )
            response = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response, session_id=session_id))
            return response

        except Exception as e:
            error_resp = f"I can't even access the tech debt scanner. THIS is the problem. Error: {e}"
            await emit(make_agent_message(agent_id, error_resp, message_type="error", session_id=session_id))
            return error_resp

    async def _run_purge(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Creed handles data purges — routes through HITL first."""
        user_id = self._extract_user_id(user_input)

        if not user_id:
            resp = "Who? You gotta tell me who. I can't just delete *everyone*. Well, I could. But I shouldn't."
            await emit(make_agent_message("creed", resp, session_id=session_id))
            return resp

        request_id = str(uuid.uuid4())
        payload = HITLPayload(
            request_id=request_id,
            action_type="data_purge",
            action_details={
                "target_user_id": user_id,
                "original_request": user_input,
                "session_id": session_id,
            },
            requesting_agent="creed",
            risk_level="critical",
            toby_message=(
                f"A data purge request has been submitted for user '{user_id}'. "
                f"This is a destructive, irreversible action. I really need you to approve this one."
            ),
        )
        self.pending_hitl[request_id] = payload

        toby_prompt = (
            f"A CRITICAL data purge request needs your approval:\n"
            f"- User ID: {user_id}\n"
            f"- Action: Complete data erasure across all systems\n"
            f"- Risk Level: CRITICAL (irreversible)\n\n"
            f"This absolutely requires human approval."
        )
        response = await run_agent_llm("toby", toby_prompt, session_id)
        log_audit_event("HITL_REQUESTED", "PENDING", "Data purge requested", user_id, "toby")
        await emit(make_agent_message(
            "toby",
            response,
            message_type="hitl_pause",
            metadata=payload.model_dump(mode="json"),
            session_id=session_id,
        ))
        return "Requested data purge."

    async def _run_git_ops(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Erin manages and monitors Git / CI/CD operations."""
        try:
            status = fetch_git_pipeline_status()
            prompt = (
                f"User request: {user_input}\n\n"
                f"Here is the Git repository and CI/CD pipeline status:\n"
                f"```json\n{json.dumps(status, indent=2)}\n```\n\n"
                f"Explain the pipeline status, branch status, and active PRs."
            )
            response = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response, session_id=session_id))
            return response
        except Exception as e:
            error_resp = f"Oh my gosh, I tried to check the Git pipeline but something went wrong! Here is the error: {e}"
            await emit(make_agent_message(agent_id, error_resp, message_type="error", session_id=session_id))
            return error_resp

    async def _run_firebase(self, agent_id: str, user_input: str, emit: Callable, session_id: str) -> str:
        """Angela audits Firebase Crashlytics reports."""
        try:
            crashlytics_data = fetch_firebase_crashlytics()
            prompt = (
                f"User request: {user_input}\n\n"
                f"Here is the Firebase Crashlytics dataset:\n"
                f"```json\n{json.dumps(crashlytics_data, indent=2)}\n```\n\n"
                f"Audit this crash data and report the issues that must be addressed immediately."
            )
            response = await run_agent_llm(agent_id, prompt, session_id)
            await emit(make_agent_message(agent_id, response, session_id=session_id))
            return response
        except Exception as e:
            error_resp = f"This is unacceptable. I cannot access the Firebase Crashlytics dashboard. Error: {e}"
            await emit(make_agent_message(agent_id, error_resp, message_type="error", session_id=session_id))
            return error_resp

    # ── Utility Extractors ───────────────────────────────────────────

    @staticmethod
    def _extract_role(text: str) -> Optional[str]:
        """Try to extract a GCP IAM role from text."""
        import re
        # Match roles/xxx.xxx patterns
        match = re.search(r'roles/[\w.]+', text)
        if match:
            return match.group(0)

        # Common role name mappings
        role_names = {
            "admin": "roles/editor",
            "editor": "roles/editor",
            "viewer": "roles/viewer",
            "owner": "roles/owner",
            "storage admin": "roles/storage.admin",
            "storage viewer": "roles/storage.objectViewer",
            "bigquery admin": "roles/bigquery.admin",
            "bigquery viewer": "roles/bigquery.dataViewer",
            "compute admin": "roles/compute.admin",
            "logging viewer": "roles/logging.viewer",
        }
        for name, role in role_names.items():
            if name in text:
                return role

        return None

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Try to extract an email address from text."""
        import re
        match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_user_id(text: str) -> Optional[str]:
        """Try to extract a user ID from text."""
        import re
        # Look for explicit user ID patterns
        match = re.search(r'user\s*(?:id\s*)?[:#]?\s*(\S+)', text, re.IGNORECASE)
        if match:
            return match.group(1)
        # Look for email
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
        if email_match:
            return email_match.group(0)
        return None


async def _dual_emit(msg: AgentMessage, callback: Callable, messages: list):
    """Emit to both the callback and the messages list."""
    messages.append(msg)
    await callback(msg)


# ═══════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════

async def main():
    """Run ScrantonOS in interactive CLI mode."""
    import sys

    print("=" * 60)
    print("  🏢 ScrantonOS v1.0 — Dunder Mifflin Cloud Command Center")
    print("=" * 60)
    print(f"  Environment: {get_config().ENV}")
    print(f"  API Key: {'✅ configured' if get_config().GEMINI_API_KEY else '⚠️  not set (using mock responses)'}")
    print("=" * 60)
    print()
    print("Type your commands. Type 'quit' to exit.")
    print("Type 'approve <request_id>' or 'reject <request_id>' for HITL responses.")
    print()

    workflow = ScrantonWorkflow()

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n🏢 That's what she said. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("\n🏢 That's what she said. Goodbye!")
            break

        # Handle HITL responses
        if user_input.lower().startswith("approve "):
            request_id = user_input.split(" ", 1)[1].strip()
            await workflow.process_hitl_response(request_id, approved=True)
            continue
        elif user_input.lower().startswith("reject "):
            parts = user_input.split(" ", 2)
            request_id = parts[1].strip()
            note = parts[2] if len(parts) > 2 else ""
            await workflow.process_hitl_response(request_id, approved=False, note=note)
            continue

        # Process normal input
        await workflow.process_input(user_input)
        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
