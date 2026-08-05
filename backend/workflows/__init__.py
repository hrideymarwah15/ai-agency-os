"""LangGraph workflow package: approval gate + CEO review graph + shared registry.

Graph instances are built once per event loop on a durable AsyncPostgresSaver
(postgres_dsn; setup() runs here) and shared by the approvals API and the
scheduler sweeper.
"""

from typing import Any

_ceo_graphs: dict[int, Any] = {}
_ceo_owners: dict[int, Any] = {}


async def get_ceo_review_graph() -> Any:
    """Registry singleton: one CEO review graph per event loop on a durable checkpointer.

    The AsyncPostgresSaver's async context manager must stay alive for the
    process lifetime — dropping it garbage-collects the generator and closes
    the underlying connection. The AsyncExitStack holds it open. The graph is
    keyed by event loop id so each TestClient portal loop and uvicorn's own
    loop gets a loop-bound saver (asyncio.Lock inside the saver is loop-bound).
    """
    import asyncio
    import contextlib

    loop_id = id(asyncio.get_running_loop())
    graph = _ceo_graphs.get(loop_id)
    if graph is None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from backend.database import postgres_dsn
        from backend.workflows.ceo_graph import build_ceo_review_graph

        stack = contextlib.AsyncExitStack()
        saver: Any = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(postgres_dsn())
        )
        await saver.setup()
        graph = build_ceo_review_graph(saver)
        existing = _ceo_graphs.get(loop_id)
        if existing is not None:
            return existing  # concurrent build won the race
        _ceo_owners[loop_id] = stack
        _ceo_graphs[loop_id] = graph
    return graph
