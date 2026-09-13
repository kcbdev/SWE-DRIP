"""Pipeline node implementations (registered into ``graph.py`` on import).

Node PBIs add modules here and call ``graph.register_node`` at module bottom;
``graph.build_graph`` imports this package so registration happens before
assembly. The graph stays the single assembly point.
"""

from . import aesthetic_qc, contract, copy, design_spec, placement, render, technical_qc, trend

__all__ = [
    "aesthetic_qc",
    "contract",
    "copy",
    "design_spec",
    "placement",
    "render",
    "technical_qc",
    "trend",
]
