"""Pipeline node implementations (registered into ``graph.py`` on import).

Node PBIs add modules here and call ``graph.register_node`` at module bottom;
``graph.build_graph`` imports this package so registration happens before
assembly. The graph stays the single assembly point.
"""

from . import contract, trend

__all__ = ["contract", "trend"]
