"""
Portfolio Tracker (Phase 4)
Derives flipping positions from the feedback store:
  cost    = asking price of an ad you tapped "✅ اشتريته" on
  revenue = actual sale price captured via "💰 اتباع بسعر"
Pure calculation — storage access stays in database/feedback.py.
"""

from typing import Any


def build_portfolio_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """
    positions: [{chat_id, message_id, asked_price, sold_price|None,
                 segment, timestamp}]
    Returns aggregate KPIs + per-position rows sorted newest-first.
    """
    rows: list[dict[str, Any]] = []
    for p in positions:
        cost = p.get("asked_price")
        revenue = p.get("sold_price")
        cost_f = float(cost) if cost is not None else None
        rev_f = float(revenue) if revenue is not None else None
        pnl = (rev_f - cost_f) if (rev_f is not None and cost_f is not None) else None
        roi = (pnl / cost_f * 100.0) if pnl is not None and cost_f else None
        rows.append({
            "chat_id": p.get("chat_id"),
            "message_id": p.get("message_id"),
            "segment": p.get("segment"),
            "timestamp": str(p.get("timestamp") or ""),
            "cost_egp": round(cost_f) if cost_f is not None else None,
            "revenue_egp": round(rev_f) if rev_f is not None else None,
            "pnl_egp": round(pnl) if pnl is not None else None,
            "roi_pct": round(roi, 1) if roi is not None else None,
            "status": "closed" if rev_f is not None else "open",
        })

    closed = [r for r in rows if r["status"] == "closed"]
    open_rows = [r for r in rows if r["status"] == "open"]

    realized_pnl = sum(r["pnl_egp"] for r in closed)
    total_cost_closed = sum(r["cost_egp"] or 0 for r in closed)
    wins = [r for r in closed if r["pnl_egp"] > 0]

    capital_deployed = sum(r["cost_egp"] or 0 for r in open_rows)

    return {
        "positions": rows,
        "totals": {
            "positions_total": len(rows),
            "open_positions": len(open_rows),
            "closed_positions": len(closed),
            "realized_pnl_egp": int(realized_pnl),
            "avg_roi_pct_closed": round(
                sum(r["roi_pct"] for r in closed) / len(closed), 1
            ) if closed else None,
            "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
            "capital_in_open_positions_egp": int(capital_deployed),
            "total_cost_basis_egp": int(total_cost_closed),
        },
    }
