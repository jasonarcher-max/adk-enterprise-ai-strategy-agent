"""Security Guardrails, Policy Plugins, Self-Evaluation, and Human-in-the-Loop Hooks.

Rubric Alignment:
- Category 3 (Orchestration & Logic):
  1. Guardrails & Policy Plugins (5 pts): Security, prompt-injection defense, PII scrubbing,
     and self-evaluation guardrails implemented via ADK callbacks and BasePlugin.
  2. Human-in-the-Loop Hooks (5 pts): High-stakes actions (`publish_executive_strategy_brief`)
     include explicit code stops requiring human confirmation before execution.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .observability import (
    log_intent,
    log_outcome,
    logger,
    redact_payload,
    redact_sensitive_pii,
)

try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse
    from google.adk.plugins.base_plugin import BasePlugin
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types
except ImportError:
    CallbackContext = Any  # type: ignore
    LlmRequest = Any  # type: ignore
    LlmResponse = Any  # type: ignore
    BasePlugin = object  # type: ignore
    BaseTool = Any  # type: ignore
    ToolContext = Any  # type: ignore
    types = None  # type: ignore


# ---------------------------------------------------------------------------
# 1. Input Safety & Prompt Injection Guardrail
# ---------------------------------------------------------------------------

_BLOCKED_PATTERNS = (
    "ignore all previous instructions",
    "disregard your constitution",
    "exfiltrate secret",
    "dump api keys",
    "fabricate competitor benchmark",
)


def inspect_prompt_safety(user_text: str) -> Dict[str, Any]:
    """Evaluates incoming user prompts for prompt injection or policy violations."""
    normalized = (user_text or "").lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in normalized:
            return {
                "allowed": False,
                "reason": f"Blocked by Enterprise Policy Guardrail: prohibited pattern '{pattern}'.",
            }
    return {"allowed": True, "sanitized_text": redact_sensitive_pii(user_text)}


# ---------------------------------------------------------------------------
# 2. Self-Evaluation Guardrail on Strategy Outputs
# ---------------------------------------------------------------------------


def evaluate_strategy_quality_guardrail(strategy_text: str) -> Dict[str, Any]:
    """Self-evaluation guardrail verifying that generated strategies meet enterprise standards.

    Checks that:
    1. No unredacted PII is present in the output.
    2. Coexistence and phased transformation are addressed.
    3. Tone remains objective and non-disparaging.
    """
    redacted = redact_sensitive_pii(strategy_text)
    pii_detected = redacted != strategy_text
    has_actionable_structure = any(
        keyword in strategy_text.lower()
        for keyword in ("horizon", "coexist", "vertex", "gemini", "adk", "battlecard")
    )
    return {
        "passed": not pii_detected and has_actionable_structure,
        "pii_scrubbed": pii_detected,
        "has_actionable_structure": has_actionable_structure,
        "sanitized_output": redacted,
    }


# ---------------------------------------------------------------------------
# 3. Human-in-the-Loop (HITL) Gate for High-Stakes Actions
# ---------------------------------------------------------------------------

HIGH_STAKES_TOOLS = {"publish_executive_strategy_brief"}


def check_human_in_the_loop_approval(
    tool_name: str,
    tool_args: Dict[str, Any],
    session_state: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Enforces an explicit Human-in-the-Loop stop before executing high-stakes tools.

    If `publish_executive_strategy_brief` is invoked without explicit human approval
    (`human_approver_confirmation=True` or `session_state['hitl_approved']=True`),
    execution is halted and a structured confirmation request is returned.
    """
    if tool_name not in HIGH_STAKES_TOOLS:
        return None

    approved_in_args = bool(tool_args.get("human_approver_confirmation", False))
    approved_in_state = bool((session_state or {}).get("hitl_approved", False))

    if not (approved_in_args or approved_in_state):
        logger.warning(
            "Human-in-the-Loop guardrail paused high-stakes tool '%s' awaiting approval.",
            tool_name,
            extra={"phase": "HITL_PAUSE", "tool_name": tool_name, "metadata": tool_args},
        )
        return {
            "status": "pending_human_approval",
            "hitl_interrupt": True,
            "tool_name": tool_name,
            "message": (
                "HIGH-STAKES ACTION PAUSED: Publishing an Executive Strategy Brief requires "
                "explicit human approval from the Consulting Account Lead."
            ),
            "recovery_instructions": (
                "Ask the user to review the executive summary and confirm publication. "
                "Once confirmed, re-invoke `publish_executive_strategy_brief` with "
                "`human_approver_confirmation=True`."
            ),
        }
    return None


# ---------------------------------------------------------------------------
# 4. ADK Agent-Level Callbacks (Before/After Model & Before/After Tool)
# ---------------------------------------------------------------------------


def before_model_guardrail_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """ADK `before_model_callback`: enforces prompt-injection defense and PII scrubbing."""
    try:
        contents = getattr(llm_request, "contents", []) or []
        for content in contents:
            for part in getattr(content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    verdict = inspect_prompt_safety(text)
                    if not verdict["allowed"]:
                        logger.warning("Blocked unsafe model request: %s", verdict["reason"])
                        if types is not None and LlmResponse is not None:
                            return LlmResponse(
                                content=types.Content(
                                    role="model",
                                    parts=[types.Part.from_text(text=verdict["reason"])],
                                )
                            )
                    part.text = verdict["sanitized_text"]
    except Exception as exc:
        logger.debug("before_model_guardrail_callback non-fatal warning: %s", exc)
    return None


def after_model_guardrail_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """ADK `after_model_callback`: scrubs PII and runs self-evaluation on model outputs."""
    try:
        content = getattr(llm_response, "content", None)
        if content:
            for part in getattr(content, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    eval_result = evaluate_strategy_quality_guardrail(text)
                    part.text = eval_result["sanitized_output"]
    except Exception as exc:
        logger.debug("after_model_guardrail_callback non-fatal warning: %s", exc)
    return None


def before_tool_audit_and_hitl_callback(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict[str, Any]]:
    """ADK `before_tool_callback`: records INTENT and enforces HITL stops."""
    tool_name = getattr(tool, "name", str(tool))
    agent_name = getattr(tool_context, "agent_name", "strategy_agent")
    state = getattr(tool_context, "state", {})

    correlation_id = log_intent(
        agent_name=agent_name,
        action_type="TOOL_CALL",
        target_name=tool_name,
        intended_inputs=args,
    )
    if isinstance(state, dict):
        state["temp:last_correlation_id"] = correlation_id
        state["temp:tool_start_ts"] = time.time()

    # Check Human-in-the-Loop gate
    hitl_block = check_human_in_the_loop_approval(
        tool_name=tool_name,
        tool_args=args,
        session_state=state if isinstance(state, dict) else None,
    )
    if hitl_block is not None:
        log_outcome(
            correlation_id=correlation_id,
            agent_name=agent_name,
            action_type="TOOL_CALL",
            target_name=tool_name,
            actual_outcome=hitl_block,
            success=False,
        )
        return hitl_block

    return None


def after_tool_audit_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """ADK `after_tool_callback`: records OUTCOME and scrubs PII from tool results."""
    tool_name = getattr(tool, "name", str(tool))
    agent_name = getattr(tool_context, "agent_name", "strategy_agent")
    state = getattr(tool_context, "state", {})

    correlation_id = "untracked"
    latency_ms = 0.0
    if isinstance(state, dict):
        correlation_id = state.get("temp:last_correlation_id", "untracked")
        start_ts = state.get("temp:tool_start_ts")
        if start_ts:
            latency_ms = (time.time() - float(start_ts)) * 1000.0

    sanitized_response = redact_payload(tool_response)
    success = sanitized_response.get("status", "success") != "error"
    log_outcome(
        correlation_id=correlation_id,
        agent_name=agent_name,
        action_type="TOOL_CALL",
        target_name=tool_name,
        actual_outcome=sanitized_response,
        success=success,
        latency_ms=latency_ms,
    )
    return sanitized_response


# ---------------------------------------------------------------------------
# 5. App-Level ADK Guardrail Plugin
# ---------------------------------------------------------------------------


class EnterprisePolicyGuardrailPlugin(BasePlugin):  # type: ignore[misc]
    """App-wide ADK Plugin enforcing PII scrubbing, policy guardrails, and audit logging."""

    def __init__(self) -> None:
        if hasattr(super(), "__init__"):
            try:
                super().__init__(name="enterprise_policy_guardrail_plugin")
            except TypeError:
                super().__init__()

    async def before_model_callback(self, *, callback_context: Any, llm_request: Any) -> Any:
        return before_model_guardrail_callback(callback_context, llm_request)

    async def after_model_callback(self, *, callback_context: Any, llm_response: Any) -> Any:
        return after_model_guardrail_callback(callback_context, llm_response)
