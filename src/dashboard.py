"""Simple web dashboard for bot-options — top opportunities ranking + paper portfolio."""
import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template_string, jsonify
from src.storage import OptionsStore
from src.config import Config
from src.yfinance_client import YFinanceClient

yf_client = YFinanceClient()

app = Flask(__name__)
config = Config()
store = OptionsStore(db_path=config.database_path)

NAV = """
<div style="margin-bottom:20px;">
    <a href="/" style="color:#a0a0ff;text-decoration:none;margin-right:20px;">Opportunities</a>
    <a href="/paper" style="color:#a0a0ff;text-decoration:none;">Paper Portfolio</a>
</div>
"""

OPPORTUNITIES_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>bot-options — Dashboard</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
        h1 { color: #e94560; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #16213e; padding: 12px 8px; text-align: left; font-weight: 600; color: #a0a0ff; }
        td { padding: 8px; border-bottom: 1px solid #2a2a4e; }
        tr:hover { background: #1f3050; }
        .score-high { color: #4caf50; font-weight: bold; }
        .score-mid { color: #ff9800; }
        .score-low { color: #f44336; }
        .call { color: #4caf50; }
        .put { color: #f44336; }
        .refresh { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <h1>🔍 bot-options — Opportunities</h1>
    <span class="refresh">Auto-refresh every 60s</span>
    """ + NAV + """
    <table>
        <tr>
            <th>Ticker</th>
            <th>Type</th>
            <th>Strike</th>
            <th>Exp</th>
            <th>Score</th>
            <th>Vol/OI</th>
            <th>Premium</th>
            <th>Reason</th>
            <th>Time</th>
        </tr>
        {% for row in rows %}
        <tr>
            <td>{{ row.ticker }}</td>
            <td class="{{ 'call' if row.type == 'CALL' else 'put' }}">{{ row.type }}</td>
            <td>${{ "%.1f"|format(row.strike) }}</td>
            <td>{{ row.exp }}</td>
            <td class="{{ 'score-high' if row.score >= 50 else 'score-mid' if row.score >= 30 else 'score-low' }}">
                {{ "%.0f"|format(row.score) }}/100
            </td>
            <td>{{ "%.1f"|format(row.vol_oi) }}</td>
            <td>${{ "{:,.0f}".format(row.premium) }}</td>
            <td>{{ row.reason }}</td>
            <td>{{ row.time }}</td>
        </tr>
        {% endfor %}
    </table>
    {% if not rows %}
    <p>No opportunities yet. Waiting for first scan cycle...</p>
    {% endif %}
</body>
</html>"""

PAPER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>bot-options — Paper Portfolio</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
        h1 { color: #e94560; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th { background: #16213e; padding: 12px 8px; text-align: left; font-weight: 600; color: #a0a0ff; }
        td { padding: 8px; border-bottom: 1px solid #2a2a4e; }
        tr:hover { background: #1f3050; }
        .call { color: #4caf50; }
        .put { color: #f44336; }
        .pnl-pos { color: #4caf50; font-weight: bold; }
        .pnl-neg { color: #f44336; font-weight: bold; }
        .cards { display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }
        .card { background: #16213e; padding: 20px; border-radius: 8px; min-width: 180px; }
        .card-label { color: #888; font-size: 12px; text-transform: uppercase; }
        .card-value { font-size: 24px; margin-top: 4px; }
        .refresh { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <h1>📊 Paper Portfolio</h1>
    <span class="refresh">Auto-refresh every 60s</span>
    """ + NAV + """
    <div class="cards">
        <div class="card">
            <div class="card-label">Portfolio Value</div>
            <div class="card-value">${{ "{:,.0f}".format(summary.portfolio_value) }}</div>
        </div>
        <div class="card">
            <div class="card-label">Current Cash</div>
            <div class="card-value">${{ "{:,.0f}".format(summary.cash) }}</div>
        </div>
        <div class="card">
            <div class="card-label">Realized PnL</div>
            <div class="card-value {{ 'pnl-pos' if summary.total_pnl >= 0 else 'pnl-neg' }}">
                ${{ "{:+,.0f}".format(summary.total_pnl) }}
            </div>
        </div>
        <div class="card">
            <div class="card-label">Unrealized PnL</div>
            <div class="card-value {{ 'pnl-pos' if (summary.unrealized_pnl or 0) >= 0 else 'pnl-neg' }}">
                ${{ "{:+,.0f}".format(summary.unrealized_pnl or 0) }}
            </div>
        </div>
        <div class="card">
            <div class="card-label">Open Positions</div>
            <div class="card-value">{{ summary.open_positions }}</div>
        </div>
    </div>

    <h2>Open Positions</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Ticker</th>
            <th>Type</th>
            <th>Strike</th>
            <th>Exp</th>
            <th>Entry</th>
            <th>Current</th>
            <th>Unrealized PnL</th>
            <th>Entry Spot</th>
            <th>Delta</th>
            <th>IV</th>
            <th>Entry Time</th>
        </tr>
        {% for pos in open_positions %}
        <tr>
            <td>{{ pos.id }}</td>
            <td>{{ pos.ticker }}</td>
            <td class="{{ 'call' if pos.option_type == 'C' else 'put' }}">{{ pos.option_type }}</td>
            <td>${{ "%.1f"|format(pos.strike) }}</td>
            <td>{{ pos.expiration }}</td>
            <td>${{ "%.2f"|format(pos.entry_price) }}</td>
            <td>{{ "$%.2f"|format(pos.current_price) if pos.current_price else "N/A" }}</td>
            <td class="{{ 'pnl-pos' if (pos.unrealized_pnl or 0) >= 0 else 'pnl-neg' }}">
                {% if pos.unrealized_pnl is not none %}${{ "{:+,.0f}".format(pos.unrealized_pnl) }} ({{ "{:+.1f}%".format(pos.unrealized_pnl_pct) }}){% else %}N/A{% endif %}
            </td>
            <td>${{ "%.2f"|format(pos.entry_spot) }}</td>
            <td>{{ "%.2f"|format(pos.entry_delta or 0) }}</td>
            <td>{{ "%.1f%%"|format((pos.entry_iv or 0) * 100) }}</td>
            <td>{{ pos.entry_time[:19] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% if not open_positions %}
    <p>No open positions.</p>
    {% endif %}

    <h2>Closed Positions</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Ticker</th>
            <th>Type</th>
            <th>Strike</th>
            <th>Entry</th>
            <th>Exit</th>
            <th>PnL</th>
            <th>Exit Time</th>
        </tr>
        {% for pos in history %}
        <tr>
            <td>{{ pos.id }}</td>
            <td>{{ pos.ticker }}</td>
            <td class="{{ 'call' if pos.option_type == 'C' else 'put' }}">{{ pos.option_type }}</td>
            <td>${{ "%.1f"|format(pos.strike) }}</td>
            <td>${{ "%.2f"|format(pos.entry_price) }}</td>
            <td>${{ "%.2f"|format(pos.exit_price) }}</td>
            <td class="{{ 'pnl-pos' if pos.pnl >= 0 else 'pnl-neg' }}">${{ "{:+,.0f}".format(pos.pnl) }}</td>
            <td>{{ (pos.exit_time or '')[:19] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% if not history %}
    <p>No closed positions yet.</p>
    {% endif %}
</body>
</html>"""


def _find_option_price(position, chain):
    for opt in chain.options:
        if (opt.strike == position["strike"]
                and opt.expiration == position["expiration"]
                and opt.option_type == position["option_type"]):
            mid = (opt.bid + opt.ask) / 2
            if mid > 0:
                return round(mid, 2)
            return round(opt.last, 2) if opt.last > 0 else None
    return None


@app.route("/")
def index():
    rows = []
    for ticker in config.scan_tickers:
        snap = store.get_latest(ticker)
        if not snap:
            continue
        for opt in snap.get("options", []):
            if opt.get("volume", 0) > 0 and opt.get("open_interest", 0) > 0:
                vol_oi = opt["volume"] / opt["open_interest"] if opt["open_interest"] > 0 else 0
                if vol_oi >= config.vol_oi_ratio_threshold:
                    rows.append({
                        "ticker": ticker,
                        "type": "CALL" if opt["option_type"] == "C" else "PUT",
                        "strike": opt["strike"],
                        "exp": opt.get("expiration", ""),
                        "score": 0,
                        "vol_oi": round(vol_oi, 1),
                        "premium": opt.get("last", 0) * opt.get("volume", 0) * 100,
                        "reason": "high_vol_oi" if vol_oi >= 1.0 else "unusual",
                        "time": snap["fetched_at"][:19],
                    })
    rows.sort(key=lambda x: x["vol_oi"], reverse=True)
    return render_template_string(OPPORTUNITIES_HTML, rows=rows[:50])


@app.route("/paper")
def paper():
    summary = store.get_account_summary()
    initial = config.paper_initial_balance
    summary["initial_balance"] = initial
    summary["cash"] = initial + summary["total_pnl"] - summary["total_invested"]
    open_positions = store.get_open_positions()

    # Mark-to-market for HTML view
    unrealized_total = 0.0
    if open_positions:
        tickers = list({p["ticker"] for p in open_positions})
        try:
            chains = asyncio.get_event_loop().run_until_complete(
                yf_client.fetch_multiple(tickers, max_concurrent=len(tickers))
            )
            chain_map = {c.ticker: c for c in chains}
            for pos in open_positions:
                chain = chain_map.get(pos["ticker"])
                if chain:
                    current = _find_option_price(pos, chain)
                    pos["current_price"] = current
                    if current is not None and current > 0:
                        pnl = (current - pos["entry_price"]) * pos["contracts"] * 100
                        pnl_pct = (current - pos["entry_price"]) / pos["entry_price"] * 100
                        pos["unrealized_pnl"] = round(pnl, 2)
                        pos["unrealized_pnl_pct"] = round(pnl_pct, 1)
                        unrealized_total += pnl
                    else:
                        pos["current_price"] = None
                        pos["unrealized_pnl"] = None
                        pos["unrealized_pnl_pct"] = None
                else:
                    pos["current_price"] = None
                    pos["unrealized_pnl"] = None
                    pos["unrealized_pnl_pct"] = None
        except Exception:
            for pos in open_positions:
                pos["current_price"] = None
                pos["unrealized_pnl"] = None
                pos["unrealized_pnl_pct"] = None

    summary["unrealized_pnl"] = round(unrealized_total, 2)
    summary["portfolio_value"] = round(summary["cash"] + summary["total_invested"] + unrealized_total, 2)
    summary["open_positions"] = summary.get("open_count", len(open_positions))
    history = store.get_position_history(limit=50)
    return render_template_string(PAPER_HTML, summary=summary,
                                 open_positions=open_positions, history=history)


@app.route("/api/opportunities")
def api_opportunities():
    rows = []
    for ticker in config.scan_tickers:
        snap = store.get_latest(ticker)
        if snap:
            rows.append({"ticker": ticker, "spot": snap["underlying_price"], "option_count": snap["option_count"], "fetched_at": snap["fetched_at"]})
    return jsonify(rows)


@app.route("/api/paper/portfolio")
def api_paper_portfolio():
    summary = store.get_account_summary()
    initial = config.paper_initial_balance
    summary["initial_balance"] = initial
    summary["cash"] = initial + summary["total_pnl"] - summary["total_invested"]
    open_positions = store.get_open_positions()

    # Mark-to-market pricing
    unrealized_total = 0.0
    if open_positions:
        tickers = list({p["ticker"] for p in open_positions})
        try:
            chains = asyncio.get_event_loop().run_until_complete(
                yf_client.fetch_multiple(tickers, max_concurrent=len(tickers))
            )
            chain_map = {c.ticker: c for c in chains}

            for pos in open_positions:
                chain = chain_map.get(pos["ticker"])
                if not chain:
                    pos["current_price"] = None
                    pos["unrealized_pnl"] = None
                    pos["unrealized_pnl_pct"] = None
                    continue

                current = _find_option_price(pos, chain)
                pos["current_price"] = current
                if current is not None and current > 0:
                    pnl = (current - pos["entry_price"]) * pos["contracts"] * 100
                    pnl_pct = (current - pos["entry_price"]) / pos["entry_price"] * 100
                    pos["unrealized_pnl"] = round(pnl, 2)
                    pos["unrealized_pnl_pct"] = round(pnl_pct, 1)
                    unrealized_total += pnl
                else:
                    pos["unrealized_pnl"] = None
                    pos["unrealized_pnl_pct"] = None
        except Exception:
            for pos in open_positions:
                pos["current_price"] = None
                pos["unrealized_pnl"] = None
                pos["unrealized_pnl_pct"] = None
    else:
        for pos in open_positions:
            pos["current_price"] = None
            pos["unrealized_pnl"] = None
            pos["unrealized_pnl_pct"] = None

    summary["unrealized_pnl"] = round(unrealized_total, 2)
    summary["portfolio_value"] = round(summary["cash"] + summary["total_invested"] + unrealized_total, 2)
    summary["open_positions"] = summary.get("open_count", len(open_positions))
    summary["open_positions_data"] = open_positions
    summary["history"] = store.get_position_history(limit=50)
    return jsonify(summary)


def main():
    port = int(os.getenv("DASHBOARD_PORT", "3001"))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main()
