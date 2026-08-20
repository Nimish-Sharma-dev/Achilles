"""
graph.py — device graph model + blast-radius traversal (Person B).

Builds a NetworkX graph straight from the shared `nodes`/`edges` tables —
deliberately NOT a static import of topology.py, so it reflects whatever
the simulator has actually seeded (matches the doc's "edges = observed
comms, not assumed" principle) and stays live if the topology ever
changes without a redeploy.

detection.py uses blast_radius() to attach an impact estimate to every
alert. dashboard.py (Person C) can import build_graph()/blast_radius()
directly too — this module owns the graph model, nobody else should be
building their own NetworkX graph from scratch.
"""

import networkx as nx

import db


def build_graph():
    conn = db.get_conn()
    G = nx.DiGraph()
    for r in conn.execute("SELECT id, type, status, risk_score, x, y FROM nodes"):
        G.add_node(
            r["id"], type=r["type"], status=r["status"],
            risk_score=r["risk_score"], x=r["x"], y=r["y"],
        )
    for r in conn.execute("SELECT source, target, protocol FROM edges"):
        if r["source"] in G and r["target"] in G:
            G.add_edge(r["source"], r["target"], protocol=r["protocol"])
    conn.close()
    return G


def blast_radius(G, node_id):
    """Everything a compromise at node_id could plausibly reach:

    downstream = nodes it can send commands/data to (control-path risk —
                 e.g. a tampered relay sending bad trip commands to meters)
    upstream   = nodes that could reach/impersonate it (pivot-path risk —
                 e.g. a compromised RTU feeding it falsified GOOSE messages)

    Returned as a plain dict so it's JSON-serializable straight into the
    ledger payload and easy for the dashboard to render without needing
    NetworkX itself.
    """
    if node_id not in G:
        return {"node": node_id, "downstream": [], "upstream": [], "total_affected": []}
    downstream = nx.descendants(G, node_id)
    upstream = nx.ancestors(G, node_id)
    return {
        "node": node_id,
        "downstream": sorted(downstream),
        "upstream": sorted(upstream),
        "total_affected": sorted(downstream | upstream),
    }


def graph_summary(G):
    """Quick header stats for the dashboard / a sanity check on stage."""
    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "components": nx.number_weakly_connected_components(G) if G.number_of_nodes() else 0,
    }