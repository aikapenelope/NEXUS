"""WebSocket streaming for NEXUS agents.

Adapted from vstorm full_app WebSocket pattern. Provides real-time
streaming of agent execution: text deltas, tool calls, tool results,
approval requests, todos updates, and cancellation.

Protocol:
  Client -> Server:
    {"session_id": "xxx", "message": "..."}  -- start/continue conversation
    {"cancel": true}                          -- cancel running agent
    {"approval": {"tool_call_id": true/false}} -- approve/deny tool execution

  Server -> Client:
    {"type": "start"}                         -- agent run started
    {"type": "text_delta", "content": "..."}  -- streaming text chunk
    {"type": "tool_start", "tool_name": "...", "args": {...}}
    {"type": "tool_output", "tool_name": "...", "output": "..."}
    {"type": "todos_update", "todos": [...]}
    {"type": "approval_required", "requests": [...]}
    {"type": "response", "content": "..."}    -- final response
    {"type": "done"}                          -- agent run complete
    {"type": "error", "content": "..."}       -- error occurred
    {"type": "cancelled"}                     -- run was cancelled
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic_ai import (
    Agent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
    ThinkingPartDelta,
    ToolCallPartDelta,
)
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults, ToolApproved, ToolDenied
from pydantic_ai.usage import UsageLimits
from pydantic_deep import DeepAgentDeps

from app.agents.definitions import CODING_AGENTS
from app.agents.factory import AgentConfig, _resolve_token_limit, build_agent
from app.sessions import session_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Streaming session state (wraps persistent Session with async runtime)
# ---------------------------------------------------------------------------


@dataclass
class StreamingSession:
    """Wraps a persistent Session with async runtime state."""

    session_id: str
    config: AgentConfig
    deps: DeepAgentDeps
    message_history: list[Any] = field(default_factory=list)
    pending_approval: dict[str, Any] = field(default_factory=dict)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    running_task: asyncio.Task[None] | None = field(default=None)
    _streamed_text: str = ""


# Active streaming sessions
_streaming: dict[str, StreamingSession] = {}


def _get_or_create_session(
    session_id: str | None,
    config: AgentConfig,
) -> StreamingSession:
    """Get existing streaming session or create with persistent backend."""
    sid = session_id or str(uuid.uuid4())

    if sid in _streaming:
        return _streaming[sid]

    # Create persistent session via SessionManager (LocalBackend on disk)
    persistent = session_manager.get_or_create(sid, config)

    session = StreamingSession(
        session_id=sid,
        config=config,
        deps=persistent.deps,
        message_history=persistent.message_history,
    )
    _streaming[sid] = session
    return session


# ---------------------------------------------------------------------------
# Streaming execution
# ---------------------------------------------------------------------------


async def _run_streaming(
    websocket: WebSocket,
    session: StreamingSession,
    user_message: str,
    deferred_results: DeferredToolResults | None = None,
) -> None:
    """Run agent with streaming events sent via WebSocket."""
    agent = build_agent(session.config)
    # Cap tokens for WebSocket sessions (testing mode)
    token_limit = min(_resolve_token_limit(session.config), 15000)

    usage_limits = UsageLimits(
        total_tokens_limit=token_limit,
        request_limit=10,
        tool_calls_limit=20,
    )

    await websocket.send_json({"type": "start"})

    session._streamed_text = ""

    async with agent.iter(
        user_message if deferred_results is None else None,
        deps=session.deps,
        message_history=session.message_history,
        usage_limits=usage_limits,
        deferred_tool_results=deferred_results,
    ) as run:
        async for node in run:
            if session.cancel_event.is_set():
                break
            await _process_node(websocket, node, run, session)

        result = run.result

    # result can be None if cancelled
    if result is None:
        await websocket.send_json({"type": "done"})
        return

    # Handle DeferredToolRequests (approval needed)
    if isinstance(result.output, DeferredToolRequests):
        session.pending_approval = {
            "message_history": result.all_messages(),
            "approvals": result.output.approvals,
        }

        requests = []
        for call in result.output.approvals:
            requests.append({
                "tool_call_id": call.tool_call_id,
                "tool_name": call.tool_name,
                "args": call.args if isinstance(call.args, dict) else str(call.args),
            })

        await websocket.send_json({
            "type": "approval_required",
            "requests": requests,
        })
        return

    # Update session history
    session.message_history = result.all_messages()

    # Persist history to disk (survives restarts)
    persistent = session_manager.get(session.session_id)
    if persistent is not None:
        persistent.message_history = session.message_history
        persistent.save_history()

    # Send final response with usage stats
    output_str = str(result.output) if result.output else ""
    usage = result.usage()
    tokens_used = usage.total_tokens if usage else 0
    cost_usd = round(tokens_used * 3.0 / 1_000_000, 4)  # rough estimate

    await websocket.send_json({
        "type": "response",
        "content": output_str,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
    })
    await websocket.send_json({"type": "done"})


async def _process_node(
    websocket: WebSocket,
    node: Any,
    run: Any,
    session: StreamingSession,
) -> None:
    """Process a single node and send WebSocket events."""
    if Agent.is_model_request_node(node):
        await _stream_model_request(websocket, node, run, session)
    elif Agent.is_call_tools_node(node):
        await _stream_tool_calls(websocket, node, run, session)


async def _stream_model_request(
    websocket: WebSocket,
    node: Any,
    run: Any,
    session: StreamingSession,
) -> None:
    """Stream text/thinking/tool-call deltas from model request."""
    current_tool_name: str | None = None

    async with node.stream(run.ctx) as request_stream:
        async for event in request_stream:
            if session.cancel_event.is_set():
                break

            if isinstance(event, PartStartEvent):
                part = event.part
                if hasattr(part, "tool_name") and getattr(part, "tool_name", None):
                    current_tool_name = part.tool_name  # type: ignore[union-attr]
                    await websocket.send_json({
                        "type": "tool_call_start",
                        "tool_name": current_tool_name,
                    })

            elif isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta):
                    await websocket.send_json({
                        "type": "text_delta",
                        "content": event.delta.content_delta,
                    })
                    session._streamed_text += event.delta.content_delta
                elif isinstance(event.delta, ThinkingPartDelta):
                    await websocket.send_json({
                        "type": "thinking_delta",
                        "content": event.delta.content_delta,
                    })
                elif isinstance(event.delta, ToolCallPartDelta):
                    await websocket.send_json({
                        "type": "tool_args_delta",
                        "tool_name": current_tool_name,
                        "args_delta": event.delta.args_delta,
                    })

            elif isinstance(event, FinalResultEvent):
                break


async def _stream_tool_calls(
    websocket: WebSocket,
    node: Any,
    run: Any,
    session: StreamingSession,
) -> None:
    """Stream tool call and result events."""
    tool_names: dict[str, str] = {}

    async with node.stream(run.ctx) as handle_stream:
        async for event in handle_stream:
            if session.cancel_event.is_set():
                break

            if isinstance(event, FunctionToolCallEvent):
                tool_name = event.part.tool_name
                tool_args = event.part.args
                tool_call_id = event.part.tool_call_id

                if tool_call_id:
                    tool_names[tool_call_id] = tool_name

                await websocket.send_json({
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "args": tool_args if isinstance(tool_args, dict) else str(tool_args),
                })

                # Send todos update if write_todos was called
                if tool_name == "write_todos":
                    try:
                        args_dict = (
                            tool_args if isinstance(tool_args, dict)
                            else json.loads(str(tool_args))
                        )
                        todos = args_dict.get("todos", [])
                        await websocket.send_json({"type": "todos_update", "todos": todos})
                    except Exception:
                        pass

            elif isinstance(event, FunctionToolResultEvent):
                tool_call_id = event.tool_call_id
                tool_name = tool_names.get(tool_call_id, "unknown")
                output = str(event.result.content)

                # Truncate large outputs for WebSocket
                if len(output) > 5000:
                    output = output[:5000] + "\n... (truncated)"

                await websocket.send_json({
                    "type": "tool_output",
                    "tool_name": tool_name,
                    "output": output,
                })


# ---------------------------------------------------------------------------
# Approval handling
# ---------------------------------------------------------------------------


async def _handle_approval(
    websocket: WebSocket,
    session: StreamingSession,
    approval_response: dict[str, bool],
) -> None:
    """Handle approval response and continue agent execution."""
    if not session.pending_approval:
        await websocket.send_json({"type": "error", "content": "No pending approval"})
        return

    approvals: dict[str, Any] = {}
    for tool_call_id, approved in approval_response.items():
        if approved:
            approvals[tool_call_id] = ToolApproved()
        else:
            approvals[tool_call_id] = ToolDenied("User denied this tool call.")

    session.message_history = session.pending_approval["message_history"]
    session.pending_approval = {}

    await _run_streaming(
        websocket,
        session,
        "",
        deferred_results=DeferredToolResults(approvals=approvals),
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


async def websocket_agent(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming agent execution.

    Mount this on the FastAPI app:
        app.add_api_websocket_route("/ws/agent", websocket_agent)
    """
    await websocket.accept()

    session: StreamingSession | None = None
    incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def _reader() -> None:
        try:
            while True:
                data = await websocket.receive_text()
                await incoming.put(json.loads(data))
        except WebSocketDisconnect:
            await incoming.put({"__disconnect": True})

    reader_task = asyncio.create_task(_reader())

    try:
        while True:
            msg = await incoming.get()

            if msg.get("__disconnect"):
                break

            # Cancel request
            if msg.get("cancel"):
                if session and session.running_task and not session.running_task.done():
                    session.cancel_event.set()
                    session.running_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await session.running_task
                    session.running_task = None
                    await websocket.send_json({"type": "cancelled"})
                    await websocket.send_json({"type": "done"})
                continue

            # Approval response
            if msg.get("approval") and session:
                session.running_task = asyncio.create_task(
                    _run_task(websocket, session, "", msg["approval"])
                )
                continue

            # New message
            user_message = msg.get("message", "")
            if not user_message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            # Get or create session
            session_id = msg.get("session_id")
            agent_name = msg.get("agent", "nexus-developer")

            if session is None:
                config = CODING_AGENTS.get(agent_name)
                if config is None:
                    # Fallback: minimal config
                    config = AgentConfig(
                        name=agent_name,
                        description="coding agent",
                        instructions="You are a coding assistant.",
                        role="analysis",
                        include_todo=True,
                        include_filesystem=True,
                        use_sandbox=False,
                        token_limit=30000,
                        cost_budget_usd=0.50,
                    )
                else:
                    # Override sandbox for WebSocket sessions (LocalBackend,
                    # no Docker). This prevents DeferredToolRequests from
                    # execute approval which the streaming handler supports
                    # but causes issues with the agent not using tools.
                    config = AgentConfig(
                        **{**config.__dict__, "use_sandbox": False}
                    )
                session = _get_or_create_session(session_id, config)
                if not session_id:
                    await websocket.send_json({
                        "type": "session_created",
                        "session_id": session.session_id,
                    })

            # Cancel previous run if still going
            if session.running_task and not session.running_task.done():
                session.cancel_event.set()
                session.running_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await session.running_task

            session.cancel_event.clear()
            session.running_task = asyncio.create_task(
                _run_task(websocket, session, user_message, None)
            )

    finally:
        reader_task.cancel()
        if session and session.running_task and not session.running_task.done():
            session.running_task.cancel()


async def _run_task(
    websocket: WebSocket,
    session: StreamingSession,
    user_message: str,
    approval: dict[str, bool] | None,
) -> None:
    """Wrapper that runs the agent and handles errors."""
    try:
        if approval:
            await _handle_approval(websocket, session, approval)
        else:
            await _run_streaming(websocket, session, user_message)
    except asyncio.CancelledError:
        # Save partial history on cancel
        if session._streamed_text:
            session.message_history.append(
                ModelRequest(parts=[UserPromptPart(content=user_message)])
            )
            session.message_history.append(
                ModelResponse(
                    parts=[TextPart(content=session._streamed_text + "\n\n[Cancelled]")]
                )
            )
        raise
    except Exception as e:
        logger.exception("Error in agent streaming run")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.send_json({"type": "done"})
        except Exception:
            pass
