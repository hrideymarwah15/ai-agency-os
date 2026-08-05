"""LangGraph workflow package: approval gate + CEO review graph + shared registry.

Graph instances are built once in the module registry on the durable
AsyncPostgresSaver (postgres_dsn; setup() already ran in the app lifespan)
and reused by the approvals API and the scheduler sweeper.
"""

from typing import Any

_ceo_graph: Any = None
_ceo_saver: Any = None


async def get_ceo_review_graph() -> Any:
    """Registry singleton: one CEO review graph per process on the durable checkpointer.

    The checkpointer pool stays open for the process lifetime; both the
    POST /approvals/demo/start trigger and the approval sweeper share it.
    """
    global _ceo_graph, _ceo_saver
    if _ceo_graph is None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from backend.database import postgres_dsn
        from backend.workflows.ceo_graph import build_ceo_review_graph

        # process-lifetime saver (lifespan ran setup()) — enter the context
        # manager explicitly, then keep the pool open for the process lifetime
        saver: Any = await AsyncPostgresSaver.from_conn_string(postgres_dsn()).__aenter__()
        await saver.setup()
        _ceo_saver = saver
        _ceo_graph = build_ceo_review_graph(saver)
    return _ceo_graph
