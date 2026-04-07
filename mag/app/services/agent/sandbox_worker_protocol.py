"""
Sandbox worker protocol helpers.

This module defines a stable payload contract used by host-side runtime router
when communicating with sandbox workers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def build_runtime_payload(
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
) -> Dict[str, Any]:
    return {
        "agent_name": agent_name,
        "user_prompt": user_prompt,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "model_name": model_name,
        "system_prompt": system_prompt,
        "mcp_servers": mcp_servers or [],
        "system_tools": system_tools or [],
        "max_iterations": max_iterations,
        "original_query": original_query,
    }


def parse_worker_stdout_events(stdout: str) -> List[Dict[str, Any]]:
    """Parse JSON-line events emitted by sandbox worker scripts.

    Non-JSON lines are wrapped as runtime log events to avoid losing diagnostics.
    """
    events: List[Dict[str, Any]] = []
    for raw_line in (stdout or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                events.append(data)
            else:
                events.append({"type": "runtime", "phase": "worker_output", "data": data})
        except Exception:
            events.append({"type": "runtime", "phase": "worker_output", "message": line})
    return events
