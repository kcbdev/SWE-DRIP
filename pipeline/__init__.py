"""SWE Drip LangGraph pipeline package.

PBI-010 foundation: 11-node ``StateGraph`` assembly (``graph.py``, the single
assembly point), typed run state (``state.py``), per-node OpenRouter routing
(``routing.py``), httpx model client (``llm.py``), cost logging (``costs.py``),
and the checkpointer factory (``checkpoint.py``). Real node implementations
land in PBI-011 onward and register via ``graph.register_node``. This package
is imported by the API — the pipeline is a library, not a separate deployable
(ADR-002).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
