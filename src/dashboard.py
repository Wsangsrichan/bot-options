"""Simple web dashboard for bot-options — top opportunities ranking."""
from flask import Flask, render_template_string, jsonify
from src.storage import OptionsStore
from src.config import Config

app = Flask(__name__)
config = Config()
store = OptionsStore(db_path=config.database_path)

INDEX_HTML = """<!DOCTYPE html>
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
    return render_template_string(INDEX_HTML, rows=rows[:50])

@app.route("/api/opportunities")
def api_opportunities():
    rows = []
    for ticker in config.scan_tickers:
        snap = store.get_latest(ticker)
        if snap:
            rows.append({"ticker": ticker, "spot": snap["underlying_price"], "option_count": snap["option_count"], "fetched_at": snap["fetched_at"]})
    return jsonify(rows)

def main():
    import os
    port = int(os.getenv("DASHBOARD_PORT", "3001"))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main()
