"""MCP2 initialization hooks.

We lazily load disk-backed user server list on first request, but having an explicit init
makes it easier to integrate with app startup if needed.
"""

from app.services.mcp2.mcp2_manager import mcp2_manager


async def init_mcp2_state() -> None:
    await mcp2_manager._ensure_user_servers_loaded()  # noqa: SLF001 (internal helper)
    # Start idle cleanup loop now that we're inside an event loop (FastAPI lifespan).
    try:
        mcp2_manager.start_cleanup_loop()
    except RuntimeError:
        # If called outside a running loop (shouldn't happen in lifespan), ignore.
        pass
