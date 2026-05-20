"""Web Dashboard — 即時多股監控畫面 (Flask + SSE)
Usage: python web_dashboard.py [--port 5000]
"""
import argparse
import csv
import json
import os
import queue
import time
import threading
from flask import Flask, Response, render_template_string, jsonify

app = Flask(__name__)
sse_queue = queue.Queue()

STOCKS = ["2330", "2317", "2344"]
DATA_INTERVAL = 2
HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yuanta OneAPI 即時監控</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:'Microsoft YaHei',sans-serif;padding:16px}
h1{font-size:20px;margin-bottom:12px;color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.card h2{font-size:16px;display:flex;justify-content:space-between}
.card .type{font-size:10px;padding:1px 6px;border-radius:10px;color:#fff}
.type-large{background:#238636}.type-mid{background:#9e6a03}.type-small{background:#6e7681}.type-spec{background:#da3633}
.row{display:flex;justify-content:space-between;margin:4px 0;font-size:13px}
.price{font-size:22px;font-weight:bold}
.up{color:#3fb950}.down{color:#f85149}.muted{color:#8b949e}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:bold}
.tag-buy{background:#238636;color:#fff}.tag-strong-buy{background:#1f6feb;color:#fff}
.tag-sell{background:#da3633;color:#fff}.tag-strong-sell{background:#9e6a03;color:#fff}
.tag-churn{background:#6e7681;color:#fff}
.bar{height:4px;border-radius:2px;margin-top:4px;background:#21262d}
.bar-fill{height:100%;border-radius:2px;transition:width .3s}
.last-update{font-size:10px;color:#484f58;margin-top:6px}
</style>
</head>
<body>
<h1>Yuanta OneAPI — 即時監控</h1>
<div class="grid" id="grid"></div>
<div class="last-update" id="status">等待資料...</div>
<script>
const cards={};
function fmt(n,d=2){return n!=null?Number(n).toFixed(d):'--'}
function vol(n){return n!=null?Math.round(n/1000).toLocaleString():'--'}
function badge(type){
  const m={large_cap:['大型','type-large'],mid_cap:['中型','type-mid'],
            small_cap:['小型','type-small'],speculative:['投機','type-spec']};
  const [label,cls]=m[type]||['--',''];
  return `<span class="${cls}">${label}</span>`;
}
function tag(label){
  const map={主力強力買進:['強力買進','tag-strong-buy'],主力溫和買進:['溫和買進','tag-buy'],
             散戶盤整:['盤整','tag-churn'],主力溫和賣出:['溫和賣出','tag-sell'],
             主力強力賣出:['強力賣出','tag-strong-sell']};
  const [text,cls]=map[label]||[label,'tag-churn'];
  return `<span class="tag ${cls}">${text}</span>`;
}
function render(data){
  const g=document.getElementById('grid');g.innerHTML='';
  for(const [id,s] of Object.entries(data)){
    const cls=s.close_price>=s.open_price?'up':'down';
    const pct=s.price_diff&&s.open_price?((s.price_diff/s.open_price)*100).toFixed(2):'--';
    const inRatio=s.total_in_volume+s.total_out_volume>0
      ?((s.total_in_volume/(s.total_in_volume+s.total_out_volume))*100).toFixed(1):50;
    g.innerHTML+=`<div class="card">
<h2>${s.stock_id} <span>${badge(s.stock_type)}</span></h2>
<div class="price ${cls}">${fmt(s.close_price)} <span style="font-size:13px">${pct>0?'+'+pct:pct}%</span></div>
<div class="row"><span>開 ${fmt(s.open_price)}</span><span>高 ${fmt(s.high_price)}</span><span>低 ${fmt(s.low_price)}</span></div>
<div class="row"><span>量 ${vol(s.deal_volume)} 張</span><span>成交筆數 ${(s.trade_count||0).toLocaleString()}</span></div>
<div class="row"><span>內盤 ${vol(s.total_in_volume)} 張</span><span class="muted">外盤 ${vol(s.total_out_volume)} 張</span></div>
<div class="row"><span>估日量 ${vol(s.estimated_day_volume)} 張</span><span class="muted">昨均% ${s.pct_of_yesterday_avg||'--'}%</span></div>
<div class="row"><span>MA5 ${fmt(s.ma5)}</span><span class="muted">MA10 ${fmt(s.ma10)}</span><span>${tag(s.participation_label||'N/A')}</span></div>
<div class="bar"><div class="bar-fill" style="width:${Math.min(100,Math.max(0,inRatio))}%;background:${inRatio>55?'#3fb950':inRatio<45?'#f85149':'#6e7681'}"></div></div>
<div class="row"><span class="muted">買盤佔比 ${inRatio}%</span><span class="muted">Score: ${s.participation_score||'--'}</span></div>
</div>`;
  }
  document.getElementById('status').textContent='更新 '+new Date().toLocaleTimeString();
}
const es=new EventSource('/stream');
es.onmessage=function(e){render(JSON.parse(e.data))};
</script>
</body>
</html>"""


def read_latest_csv(stock_id: str) -> dict | None:
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        row = rows[-1]
        return {
            "stock_id": row.get("stock_id", stock_id),
            "close_price": _num(row, "close_price"),
            "open_price": _num(row, "open_price"),
            "high_price": _num(row, "high_price"),
            "low_price": _num(row, "low_price"),
            "price_diff": _num(row, "price_diff"),
            "deal_volume": _num(row, "deal_volume", int),
            "trade_count": _num(row, "trade_count", int),
            "total_in_volume": _num(row, "total_in_volume", int),
            "total_out_volume": _num(row, "total_out_volume", int),
            "estimated_day_volume": _num(row, "estimated_day_volume", int),
            "pct_of_yesterday_avg": _num(row, "pct_of_yesterday_avg"),
            "ma5": _num(row, "ma5"),
            "ma10": _num(row, "ma10"),
            "stock_type": row.get("stock_type", "unknown"),
            "participation_score": _num(row, "participation_score"),
            "participation_label": row.get("participation_label", "N/A"),
        }
    except Exception:
        return None


def _num(row, key, cast=float):
    try:
        v = row.get(key)
        if v is None or v == "":
            return None
        return cast(v)
    except (ValueError, TypeError):
        return None


def poll_worker():
    last_mtimes = {}
    while True:
        data = {}
        for sid in STOCKS:
            path = f"{sid}.csv"
            try:
                mt = os.path.getmtime(path) if os.path.exists(path) else 0
                if mt != last_mtimes.get(sid, 0):
                    last_mtimes[sid] = mt
                    rec = read_latest_csv(sid)
                    if rec:
                        data[sid] = rec
            except OSError:
                pass
        if data:
            sse_queue.put(data)
        time.sleep(DATA_INTERVAL)


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                data = sse_queue.get(timeout=30)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/stocks")
def api_stocks():
    result = {}
    for sid in STOCKS:
        rec = read_latest_csv(sid)
        if rec:
            result[sid] = rec
    return jsonify(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    poll_thread = threading.Thread(target=poll_worker, daemon=True)
    poll_thread.start()

    print(f"Dashboard → http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
