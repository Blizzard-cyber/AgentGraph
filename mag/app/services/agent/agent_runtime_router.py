"""
Agent runtime router.

Phase 1 goals:
- Introduce runtime selection (local / sandbox) for single-agent runs.
- Integrate OpenShell sandbox lifecycle preflight.
- Keep current agent execution behavior compatible by delegating to local executor.

Notes:
- In phase 1, sandbox mode performs environment preflight in OpenShell and then
  runs the existing local executor path to preserve behavior.
- Later phases can move the full agent loop into sandbox worker execution.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import AsyncGenerator, Optional, List

from app.core.config import settings
from app.services.agent.agent_stream_executor import AgentStreamExecutor
from app.services.agent.sandbox_worker_protocol import (
    build_runtime_payload,
    parse_worker_stdout_events,
)

logger = logging.getLogger(__name__)


class AgentRuntimeRouter:
    """Routes agent execution to runtime backend."""

    def __init__(self, local_executor: AgentStreamExecutor):
        self._local_executor = local_executor

    def resolve_runtime_mode(self, runtime_mode: Optional[str]) -> str:
        mode = (runtime_mode or settings.AGENT_RUNTIME_MODE or "local").strip().lower()
        if mode not in {"local", "sandbox"}:
            logger.warning("Invalid runtime_mode '%s', fallback to local", mode)
            return "local"
        return mode

    async def run_agent_stream(
        self,
        *,
        runtime_mode: Optional[str],
        agent_name: Optional[str],
        user_prompt: str,
        user_id: str,
        conversation_id: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        mcp_servers: Optional[List[str]] = None,
        system_tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
        original_query: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        mode = self.resolve_runtime_mode(runtime_mode)
        if mode == "sandbox":
            async for item in self._run_agent_stream_with_sandbox_preflight(
                agent_name=agent_name,
                user_prompt=user_prompt,
                user_id=user_id,
                conversation_id=conversation_id,
                model_name=model_name,
                system_prompt=system_prompt,
                mcp_servers=mcp_servers,
                system_tools=system_tools,
                max_iterations=max_iterations,
                original_query=original_query,
            ):
                yield item
            return

        async for item in self._local_executor.run_agent_stream(
            agent_name=agent_name,
            user_prompt=user_prompt,
            user_id=user_id,
            conversation_id=conversation_id,
            model_name=model_name,
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            system_tools=system_tools,
            max_iterations=max_iterations,
            original_query=original_query,
        ):
            yield item

    async def _run_agent_stream_with_sandbox_preflight(
        self,
        *,
        agent_name: Optional[str],
        user_prompt: str,
        user_id: str,
        conversation_id: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        mcp_servers: Optional[List[str]] = None,
        system_tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
        original_query: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        sandbox_ok = False
        worker_probe_ok = False
        worker_entry_ok = False
        worker_streamed = False
        sandbox_id = None
        worker_events: List[dict] = []
        runtime_payload = build_runtime_payload(
            agent_name=agent_name,
            user_prompt=user_prompt,
            user_id=user_id,
            conversation_id=conversation_id,
            model_name=model_name,
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            system_tools=system_tools,
            max_iterations=max_iterations,
            original_query=original_query,
        )

        try:
            from openshell import Sandbox

            # Phase 1 preflight: ensure sandbox can be created and execute basic commands.
            with Sandbox(
                cluster=settings.OPENSHELL_CLUSTER_NAME or None,
                delete_on_exit=settings.OPENSHELL_DELETE_ON_EXIT,
                timeout=settings.OPENSHELL_CLIENT_TIMEOUT,
                ready_timeout_seconds=settings.OPENSHELL_READY_TIMEOUT_SECONDS,
            ) as sb:
                sandbox_id = sb.id
                preflight = sb.exec(
                    ["python", "--version"],
                    timeout_seconds=settings.OPENSHELL_EXEC_TIMEOUT_SECONDS,
                )
                sandbox_ok = preflight.exit_code == 0

                if sandbox_ok and settings.AGENT_SANDBOX_EXEC_MODE == "worker_probe":
                    worker_probe = sb.exec(
                        ["python", "-c", _SANDBOX_WORKER_PROBE_SCRIPT],
                        env={
                            "AGENT_RUNTIME_PAYLOAD_B64": base64.b64encode(
                                json.dumps(runtime_payload, ensure_ascii=False).encode("utf-8")
                            ).decode("ascii")
                        },
                        timeout_seconds=settings.OPENSHELL_EXEC_TIMEOUT_SECONDS,
                    )
                    worker_probe_ok = worker_probe.exit_code == 0
                    worker_events.extend(parse_worker_stdout_events(worker_probe.stdout))

                if sandbox_ok and settings.AGENT_SANDBOX_EXEC_MODE == "worker_entry":
                    worker_entry = sb.exec(
                        ["python", "-c", _SANDBOX_WORKER_ENTRY_SCRIPT],
                        env={
                            "AGENT_RUNTIME_PAYLOAD_B64": base64.b64encode(
                                json.dumps(runtime_payload, ensure_ascii=False).encode("utf-8")
                            ).decode("ascii")
                        },
                        timeout_seconds=settings.OPENSHELL_EXEC_TIMEOUT_SECONDS,
                    )
                    worker_entry_ok = worker_entry.exit_code == 0
                    worker_events.extend(parse_worker_stdout_events(worker_entry.stdout))

            info = {
                "type": "runtime",
                "runtime": "sandbox",
                "phase": "preflight_ok" if sandbox_ok else "preflight_failed",
                "sandbox_id": sandbox_id,
            }
            yield f"data: {json.dumps(info)}\n\n"

            if settings.AGENT_SANDBOX_EXEC_MODE == "worker_probe":
                probe_info = {
                    "type": "runtime",
                    "runtime": "sandbox",
                    "phase": "worker_probe_ok" if worker_probe_ok else "worker_probe_failed",
                    "sandbox_id": sandbox_id,
                }
                yield f"data: {json.dumps(probe_info)}\n\n"

            if settings.AGENT_SANDBOX_EXEC_MODE == "worker_entry":
                entry_info = {
                    "type": "runtime",
                    "runtime": "sandbox",
                    "phase": "worker_entry_ok" if worker_entry_ok else "worker_entry_failed",
                    "sandbox_id": sandbox_id,
                }
                yield f"data: {json.dumps(entry_info)}\n\n"

            for event in worker_events:
                if isinstance(event, dict) and event.get("type") == "worker_sse":
                    sse_data = event.get("sse")
                    if isinstance(sse_data, str) and sse_data.startswith("data: "):
                        worker_streamed = True
                        yield sse_data
                        continue

                event.setdefault("runtime", "sandbox")
                event.setdefault("type", "runtime")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("Sandbox preflight failed: %s", str(e))
            sandbox_ok = False
            err = {
                "type": "runtime",
                "runtime": "sandbox",
                "phase": "preflight_error",
                "message": str(e),
            }
            yield f"data: {json.dumps(err)}\n\n"

            if not settings.AGENT_RUNTIME_ALLOW_FALLBACK:
                yield f"data: {json.dumps({'error': {'message': f'Sandbox preflight failed: {str(e)}', 'type': 'runtime_error'}})}\n\n"
                yield "data: [DONE]\n\n"
                return

        if not sandbox_ok and not settings.AGENT_RUNTIME_ALLOW_FALLBACK:
            yield f"data: {json.dumps({'error': {'message': 'Sandbox preflight failed', 'type': 'runtime_error'}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if (
            sandbox_ok
            and settings.AGENT_SANDBOX_EXEC_MODE == "worker_probe"
            and not worker_probe_ok
            and not settings.AGENT_RUNTIME_ALLOW_FALLBACK
        ):
            yield f"data: {json.dumps({'error': {'message': 'Sandbox worker probe failed', 'type': 'runtime_error'}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if (
            sandbox_ok
            and settings.AGENT_SANDBOX_EXEC_MODE == "worker_entry"
            and not worker_entry_ok
            and not settings.AGENT_RUNTIME_ALLOW_FALLBACK
        ):
            yield f"data: {json.dumps({'error': {'message': 'Sandbox worker entry failed', 'type': 'runtime_error'}})}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not sandbox_ok and settings.AGENT_RUNTIME_ALLOW_FALLBACK:
            fallback = {
                "type": "runtime",
                "runtime": "local",
                "phase": "fallback",
                "reason": "sandbox_unavailable",
            }
            yield f"data: {json.dumps(fallback)}\n\n"

        if (
            sandbox_ok
            and settings.AGENT_SANDBOX_EXEC_MODE == "worker_probe"
            and not worker_probe_ok
            and settings.AGENT_RUNTIME_ALLOW_FALLBACK
        ):
            fallback = {
                "type": "runtime",
                "runtime": "local",
                "phase": "fallback",
                "reason": "sandbox_worker_probe_failed",
            }
            yield f"data: {json.dumps(fallback)}\n\n"

        if (
            sandbox_ok
            and settings.AGENT_SANDBOX_EXEC_MODE == "worker_entry"
            and not worker_entry_ok
            and settings.AGENT_RUNTIME_ALLOW_FALLBACK
        ):
            fallback = {
                "type": "runtime",
                "runtime": "local",
                "phase": "fallback",
                "reason": "sandbox_worker_entry_failed",
            }
            yield f"data: {json.dumps(fallback)}\n\n"

        # If worker entry completed and has streamed SSE, treat sandbox path as primary
        # and skip local executor to avoid duplicate responses.
        if (
            sandbox_ok
            and settings.AGENT_SANDBOX_EXEC_MODE == "worker_entry"
            and worker_entry_ok
            and worker_streamed
        ):
            return

        async for item in self._local_executor.run_agent_stream(
            agent_name=agent_name,
            user_prompt=user_prompt,
            user_id=user_id,
            conversation_id=conversation_id,
            model_name=model_name,
            system_prompt=system_prompt,
            mcp_servers=mcp_servers,
            system_tools=system_tools,
            max_iterations=max_iterations,
            original_query=original_query,
        ):
            yield item


_SANDBOX_WORKER_PROBE_SCRIPT = """
import base64
import json
import os

payload_b64 = os.environ.get('AGENT_RUNTIME_PAYLOAD_B64', '')
if not payload_b64:
    raise SystemExit(2)

payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))
out = {
    'status': 'ok',
    'worker': 'sandbox_probe',
    'agent_name': payload.get('agent_name'),
    'conversation_id': payload.get('conversation_id'),
}
print(json.dumps(out, ensure_ascii=False))
""".strip()


_SANDBOX_WORKER_ENTRY_SCRIPT = """
import base64
import asyncio
import json
import os

payload_b64 = os.environ.get('AGENT_RUNTIME_PAYLOAD_B64', '')
if not payload_b64:
    print(json.dumps({'type': 'runtime', 'phase': 'worker_entry_error', 'message': 'missing payload'}, ensure_ascii=False))
    raise SystemExit(2)

payload = json.loads(base64.b64decode(payload_b64).decode('utf-8'))

print(json.dumps({
    'type': 'runtime',
    'phase': 'worker_entry_start',
    'agent_name': payload.get('agent_name'),
    'conversation_id': payload.get('conversation_id'),
}, ensure_ascii=False))

try:
    from app.services.agent.agent_stream_executor import AgentStreamExecutor
except Exception as e:
    print(json.dumps({
        'type': 'runtime',
        'phase': 'worker_entry_import_missing',
        'message': str(e),
    }, ensure_ascii=False))
    raise SystemExit(3)


async def _run():
    executor = AgentStreamExecutor()
    async for chunk in executor.run_agent_stream(
        agent_name=payload.get('agent_name'),
        user_prompt=payload.get('user_prompt') or '',
        user_id=payload.get('user_id') or 'unknown',
        conversation_id=payload.get('conversation_id') or 'default',
        model_name=payload.get('model_name'),
        system_prompt=payload.get('system_prompt'),
        mcp_servers=payload.get('mcp_servers') or [],
        system_tools=payload.get('system_tools') or [],
        max_iterations=payload.get('max_iterations'),
        original_query=payload.get('original_query'),
    ):
        # Emit SSE chunk as JSON line for host-side replay.
        print(json.dumps({'type': 'worker_sse', 'sse': chunk}, ensure_ascii=False))


try:
    asyncio.run(_run())
except Exception as e:
    print(json.dumps({
        'type': 'runtime',
        'phase': 'worker_entry_execution_error',
        'message': str(e),
    }, ensure_ascii=False))
    raise SystemExit(4)
""".strip()
