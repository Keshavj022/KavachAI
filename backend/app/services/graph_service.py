"""Fraud-network graph construction and ring clustering.

Builds an in-memory ``networkx`` graph from the identifier and link tables and
returns it as JSON for the authority force-graph view. Connected components are
treated as fraud "rings" so the UI can cluster and colour them, and per-node
risk drives node colour.
"""

from __future__ import annotations

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identifier import Identifier, IdentifierLink


def build_graph(db: Session) -> dict:
    """Return ``{nodes, links}`` describing the current fraud network."""
    identifiers = list(db.scalars(select(Identifier)).all())
    links = list(db.scalars(select(IdentifierLink)).all())

    graph = nx.Graph()
    for ident in identifiers:
        graph.add_node(
            ident.id,
            label=ident.value,
            type=ident.type,
            risk=round(ident.risk_score, 3),
            reports=ident.report_count,
        )

    valid_ids = {i.id for i in identifiers}
    for link in links:
        # Guard against edges pointing at pruned nodes.
        if link.source_id in valid_ids and link.target_id in valid_ids:
            graph.add_edge(
                link.source_id,
                link.target_id,
                weight=round(link.weight, 3),
                reason=link.reason,
            )

    # Ring id = connected-component index (stable by smallest member id).
    ring_of: dict[int, int] = {}
    components = sorted(nx.connected_components(graph), key=lambda c: min(c))
    for ring_index, component in enumerate(components):
        for node_id in component:
            ring_of[node_id] = ring_index

    nodes = [
        {
            "id": node_id,
            "label": data["label"],
            "type": data["type"],
            "risk": data["risk"],
            "reports": data["reports"],
            "ring": ring_of.get(node_id, -1),
        }
        for node_id, data in graph.nodes(data=True)
    ]
    graph_links = [
        {
            "source": u,
            "target": v,
            "weight": data["weight"],
            "reason": data["reason"],
        }
        for u, v, data in graph.edges(data=True)
    ]
    return {"nodes": nodes, "links": graph_links}


def ring_summary(db: Session) -> list[dict]:
    """Summarise each ring: size, member types, peak risk.

    Only multi-node components are reported as rings (a lone identifier is not
    a ring). Used by the dashboard to headline the most dangerous clusters.
    """
    data = build_graph(db)
    by_ring: dict[int, list[dict]] = {}
    for node in data["nodes"]:
        by_ring.setdefault(node["ring"], []).append(node)

    summaries = []
    for ring_id, members in by_ring.items():
        if len(members) < 2:
            continue
        summaries.append(
            {
                "ring": ring_id,
                "size": len(members),
                "peak_risk": max(m["risk"] for m in members),
                "total_reports": sum(m["reports"] for m in members),
                "types": sorted({m["type"] for m in members}),
            }
        )
    summaries.sort(key=lambda s: (s["peak_risk"], s["size"]), reverse=True)
    return summaries
