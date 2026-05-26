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
from flask import Flask, Response, render_template_string, jsonify, request
from option_pricing import OptionPricing, put_call_ratio_analysis

app = Flask(__name__)
sse_queue = queue.Queue()

WATCHLIST_PATH = "watchlist.json"
NAMES_PATH = "stock_names.json"
_active_watchlist = "自選股1"

def load_names():
    if os.path.exists(NAMES_PATH):
        with open(NAMES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_stock_name(stock_id: str) -> str:
    return load_names().get(stock_id, stock_id)

def load_watchlists():
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"自選股1": {"stocks": ["2330", "2317", "2344"], "futures": []}}

def get_active_stocks():
    wl = load_watchlists()
    entry = wl.get(_active_watchlist, wl.get("自選股1", {"stocks": []}))
    return entry.get("stocks", [])

STOCKS = get_active_stocks()
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
.header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.wl-select{padding:6px 10px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;font-size:13px}
.wl-select:focus{outline:none;border-color:#58a6ff}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media(max-width:1200px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
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
.bar-fill{height:100%;border-radius:2px;transition:none}
.last-update{font-size:10px;color:#484f58;margin-top:6px}
.summary-bar{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:13px}
.summary-item{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px 14px}
.summary-item .num{font-size:18px;font-weight:bold}
.pcr-panel{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-top:12px}
.pcr-panel h3{font-size:14px;margin-bottom:8px}
.pcr-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.pcr-row input{width:80px;padding:4px 6px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:4px;font-size:12px}
.pcr-row label{font-size:11px;color:#8b949e}
.pcr-result{font-size:12px;margin-top:8px;line-height:1.6}
.toggle-btn{background:none;border:none;color:#58a6ff;cursor:pointer;font-size:13px;padding:4px 0}
.depth-table{width:100%;border-collapse:collapse;font-size:11px;margin-top:4px}
.depth-table th{color:#8b949e;font-weight:normal;text-align:right;padding:1px 4px}
.depth-table td{text-align:right;padding:1px 4px;font-variant-numeric:tabular-nums}
.depth-table .bid{color:#3fb950}.depth-table .ask{color:#f85149}
.stat-row{display:flex;justify-content:space-between;font-size:11px;margin-top:6px;color:#8b949e;border-top:1px solid #21262d;padding-top:4px}
</style>
</head>
<body>
<div class="header">
<h1>Yuanta OneAPI — 即時監控</h1>
<select class="wl-select" id="wlSelect" onchange="switchWatchlist(this.value)"></select>
</div>
<div class="summary-bar" id="summary"></div>
<button class="toggle-btn" id="recBtn" onclick="toggleAllRecords()">▸ 全部價量紀錄</button>
<div class="grid" id="grid"></div>
<button class="toggle-btn" onclick="document.getElementById('pcrPanel').style.display=document.getElementById('pcrPanel').style.display==='none'?'block':'none'">Put/Call 合理價計算 ▾</button>
<div class="pcr-panel" id="pcrPanel" style="display:none">
<h3>選擇權合理價評估</h3>
<div class="pcr-row">
<label>S(現貨)<input id="pcrS" value="23000"></label>
<label>K(履約)<input id="pcrK" value="23000"></label>
<label>天數<input id="pcrD" value="30"></label>
<label>Call市價<input id="pcrC" value="300"></label>
<label>Put市價<input id="pcrP" value="280"></label>
<label>波動率<input id="pcrV" value="0.25"></label>
<button onclick="calcPCR()" style="padding:4px 12px;background:#238636;border:none;color:#fff;border-radius:4px;cursor:pointer">計算</button>
</div>
<div class="pcr-result" id="pcrResult"></div>
</div>
<div class="last-update" id="status">等待資料...</div>
<script>
async function loadWatchlists(){
  const r=await fetch('/api/watchlists');const d=await r.json();
  const sel=document.getElementById('wlSelect');
  sel.innerHTML=d.watchlists.map(w=>`<option value="${w}" ${w===d.active?'selected':''}>${w}</option>`).join('');
}
async function switchWatchlist(name){
  await fetch('/api/watchlist/'+encodeURIComponent(name),{method:'POST'});
  location.reload();
}
loadWatchlists();
function fmt(n,d=2){if(n==null)return'--';return Number(n).toFixed(d);}
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
const cards={};
function cardHTML(s){
  if(s.close_price==null) return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span></h2><div class="row muted">等待資料...</div>`;
  const cls=s.close_price>=s.open_price?'up':'down';
  const pct=s.price_diff&&s.open_price?((s.price_diff/s.open_price)*100).toFixed(2):'--';
  const inRatio=s.total_in_volume+s.total_out_volume>0
    ?((s.total_in_volume/(s.total_in_volume+s.total_out_volume))*100).toFixed(1):50;
  const dealAmt=s.deal_amount||0, dealVol=s.deal_volume||0;
  let recs='';
  if(s._records&&s._records.length){
    recs='<table class="depth-table" style="margin-top:4px"><tr><th>時間</th><th>成交價</th><th>量(張)</th><th>內盤</th><th>外盤</th><th>金額</th></tr>';
    for(const r of s._records){
      recs+=`<tr><td>${r.time||'--'}</td><td>${fmt(r.price)}</td><td>${Math.round(r.vol/1000).toLocaleString()}</td><td>${Math.round(r.in_vol/1000).toLocaleString()}</td><td>${Math.round(r.out_vol/1000).toLocaleString()}</td><td>${(r.amt/1e8).toFixed(2)}億</td></tr>`;
    }
    recs+='</table>';
  }
  const uid='r'+s.stock_id;
  return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span> <span>${badge(s.stock_type)}</span></h2>
<div class="price ${cls}">${fmt(s.close_price)} <span style="font-size:13px">${pct>0?'+'+pct:pct}%</span></div>
<div class="row"><span>開 ${fmt(s.open_price)}</span><span>高 ${fmt(s.high_price)}</span><span>低 ${fmt(s.low_price)}</span></div>
<div class="row"><span>量 ${vol(dealVol)} 張</span><span>成交筆數 ${(s.trade_count||0).toLocaleString()}</span></div>
<div class="row"><span>內盤 ${vol(s.total_in_volume)} 張</span><span class="muted">外盤 ${vol(s.total_out_volume)} 張</span></div>
<div class="row"><span>估日量 ${vol(s.estimated_day_volume)} 張</span><span class="muted">昨均% ${s.pct_of_yesterday_avg||'--'}%</span></div>
<div class="row"><span>MA5 ${fmt(s.ma5)}</span><span class="muted">MA10 ${fmt(s.ma10)}</span><span>${tag(s.participation_label||'N/A')}</span></div>
<div class="bar"><div class="bar-fill" style="width:${Math.min(100,Math.max(0,inRatio))}%;background:${inRatio>55?'#3fb950':inRatio<45?'#f85149':'#6e7681'}"></div></div>
<div class="row"><span class="muted">買盤佔比 ${inRatio}%</span><span class="muted">Score: ${s.participation_score||'--'}</span></div>
<div class="stat-row"><span>${(s.timestamp||'').slice(-8)}</span><span>成交總額 ${(dealAmt/1e8).toFixed(2)}億 / ${vol(dealVol)}張</span></div>
<div class="c-recs" style="display:none">${recs}</div>`;
}
function render(data){
  const g=document.getElementById('grid'), active=new Set(Object.keys(data));
  for(const id of Object.keys(cards)){if(!active.has(id)){cards[id].remove();delete cards[id];}}
  for(const [id,s] of Object.entries(data)){
    let el=cards[id];
    if(!el){el=document.createElement('div');el.className='card';cards[id]=el;g.appendChild(el);}
    const h=cardHTML(s);if(el._h!==h){el.innerHTML=h;el._h=h;}
  }
}
function summary(data){
  let totalVol=0,totalIn=0,totalOut=0,up=0,down=0;const entries=Object.entries(data);
  for(const[,s] of entries){
    totalVol+=(s.deal_volume||0);totalIn+=(s.total_in_volume||0);totalOut+=(s.total_out_volume||0);
    if(s.close_price>=s.open_price) up++; else down++;
  }
  const inPct=totalIn+totalOut>0?Math.round(totalIn/(totalIn+totalOut)*100):50;
  const bar=document.getElementById('summary');
  if(!bar._built){bar.innerHTML='<div class="summary-item"><span class="s-cnt"></span> <span class="s-updn"></span></div><div class="summary-item">總量 <span class="num s-tvol"></span></div><div class="summary-item">內盤佔比 <span class="num s-inpct"></span></div>';bar._built=true;}
  setText(bar.querySelector('.s-cnt'),'監控 '+entries.length+' 檔');
  setText(bar.querySelector('.s-updn'),up+'↑ '+down+'↓');
  setText(bar.querySelector('.s-tvol'),Math.round(totalVol/1000).toLocaleString()+' 張');
  const pctEl=bar.querySelector('.s-inpct');setText(pctEl,inPct+'%');
  pctEl.style.color=inPct>55?'#3fb950':inPct<45?'#f85149':'#c9d1d9';
}
async function calcPCR(){
  const p=id=>document.getElementById(id).value;
  const r=await fetch('/api/options?'+new URLSearchParams({S:p('pcrS'),K:p('pcrK'),days:p('pcrD'),call:p('pcrC'),put:p('pcrP'),vol:p('pcrV')}));
  const d=await r.json();
  document.getElementById('pcrResult').innerHTML=`
理論 Call: ${d.fair_call} (市場 ${d.call_premium_pct>0?'+':''}${d.call_premium_pct}%)<br>
理論 Put: ${d.fair_put} (市場 ${d.put_premium_pct>0?'+':''}${d.put_premium_pct}%)<br>
Call IV: ${(d.call_iv*100).toFixed(1)}% | Put IV: ${(d.put_iv*100).toFixed(1)}%<br>
Parity偏差: ${d.parity_diff>0?'Call偏貴':'Put偏貴'} ${Math.abs(d.parity_diff).toFixed(1)}<br>
PCR 訊號: ${d.pcr.signal} (vol:${d.pcr.vol_ratio||'--'})`;
}
const statusEl=document.getElementById('status');
statusEl.textContent='連線中...';
(async function init(){
  try{const r=await fetch('/api/stocks');const d=await r.json();render(d);summary(d);}catch(e){}
})();
let _recsOpen=false;
function toggleAllRecords(){
  _recsOpen=!_recsOpen;
  document.getElementById('recBtn').textContent=_recsOpen?'▾ 全部價量紀錄':'▸ 全部價量紀錄';
  for(const[id,el] of Object.entries(cards)){
    const r=el.querySelector('.c-recs');if(r)r.style.display=_recsOpen?'block':'none';
  }
}
const es=new EventSource('/stream');
es.onopen=function(){statusEl.textContent='SSE 已連線'};
es.onerror=function(){statusEl.textContent='SSE 斷線，重新連線中...'};
es.onmessage=function(e){const d=JSON.parse(e.data);render(d);summary(d);statusEl.textContent='更新 '+new Date().toLocaleTimeString()};
</script>
</body>
</html>"""


def read_latest_csv(stock_id: str) -> dict | None:
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        row = rows[-1]
        buy_prices = _parse_list(row.get("buy_prices", ""))
        buy_volumes = _parse_list(row.get("buy_volumes", ""))
        sell_prices = _parse_list(row.get("sell_prices", ""))
        sell_volumes = _parse_list(row.get("sell_volumes", ""))
        buy_total_volume = _num(row, "buy_total_volume", int) or sum(int(v) for v in buy_volumes if v)
        sell_total_volume = _num(row, "sell_total_volume", int) or sum(int(v) for v in sell_volumes if v)
        buy_sell_imbalance = _num(row, "buy_sell_imbalance", int)
        if buy_sell_imbalance is None and (buy_total_volume or sell_total_volume):
            buy_sell_imbalance = (buy_total_volume or 0) - (sell_total_volume or 0)
        pct_val = row.get("pct_of_yesterday_avg", "")
        pct_of_yesterday_avg = _num(row, "pct_of_yesterday_avg")
        if pct_val == "pct_of_yesterday_avg":
            pct_of_yesterday_avg = None
        close_price = _normalize_price(_num(row, "close_price"))
        open_price = _normalize_price(_num(row, "open_price"))
        price_diff = _num(row, "price_diff")
        if price_diff is None and close_price is not None and open_price is not None:
            price_diff = round(close_price - open_price, 2)
        deal_amount = _num(row, "deal_amount")
        deal_volume = _num(row, "deal_volume", int)
        if deal_amount is None and close_price is not None and deal_volume:
            deal_amount = round(close_price * deal_volume, 0)
        stock_type = row.get("stock_type", "")
        if not stock_type or stock_type == "unknown":
            stock_type = _detect_stock_type(stock_id, close_price)
        participation_score = _num(row, "participation_score")
        participation_label = row.get("participation_label", "")
        if participation_label in ("", "N/A", "等待資料") and participation_score is not None:
            participation_label = _score_to_label(participation_score)
        elif not participation_label or participation_label in ("N/A", "等待資料"):
            total_in = _num(row, "total_in_volume", int) or 0
            total_out = _num(row, "total_out_volume", int) or 0
            if total_in + total_out > 0:
                participation_score = round((total_in - total_out) / (total_in + total_out) * 50, 1)
                participation_label = _score_to_label(participation_score)
        return {
            "stock_id": row.get("stock_id", stock_id),
            "stock_name": get_stock_name(stock_id),
            "buy_prices": buy_prices,
            "buy_volumes": buy_volumes,
            "sell_prices": sell_prices,
            "sell_volumes": sell_volumes,
            "buy_total_volume": buy_total_volume,
            "sell_total_volume": sell_total_volume,
            "buy_sell_imbalance": buy_sell_imbalance,
            "deal_amount": deal_amount,
            "close_price": close_price,
            "open_price": open_price,
            "high_price": _normalize_price(_num(row, "high_price")),
            "low_price": _normalize_price(_num(row, "low_price")),
            "price_diff": price_diff,
            "deal_volume": deal_volume,
            "trade_count": _num(row, "trade_count", int),
            "total_in_volume": _num(row, "total_in_volume", int),
            "total_out_volume": _num(row, "total_out_volume", int),
            "estimated_day_volume": _num(row, "estimated_day_volume", int),
            "pct_of_yesterday_avg": pct_of_yesterday_avg,
            "ma5": _num(row, "ma5"),
            "ma10": _num(row, "ma10"),
            "stock_type": stock_type,
            "timestamp": row.get("timestamp", ""),
            "participation_score": participation_score,
            "participation_label": participation_label if participation_label not in ("", "N/A", "等待資料") else "等待資料",
        }
    except Exception:
        return None


def _normalize_price(val):
    """將可能為 API 原始整數的價格正規化為 TWD。
    台灣個股價格合理範圍 1~10000，若超過 100000 視為原始整數 (/10000)。"""
    if val is None:
        return None
    if abs(val) > 100000:
        return round(val / 10000, 2)
    return val


def _detect_stock_type(stock_id: str, price=None) -> str:
    tw50 = {
        '2330', '2317', '2454', '2412', '2881', '2882', '2886', '2891',
        '2308', '2303', '2327', '2344', '2345', '2357', '2379', '2382',
        '2395', '2408', '3008', '3034', '3045', '3711', '4904', '4938',
        '5871', '5876', '5880', '6505', '1301', '1303', '1326', '2002',
        '2207', '2603', '2609', '2610', '2615', '2633', '2801', '2880',
        '2883', '2884', '2885', '2887', '2888', '2890', '2892', '2912',
        '3443', '3533', '3661', '5269', '6415', '8046', '8299', '8454',
    }
    if stock_id in tw50:
        return 'large_cap'
    if len(stock_id) == 4 and stock_id[0] in ('2', '3', '4', '5', '6', '8', '9'):
        return 'mid_cap'
    return 'small_cap'


def _score_to_label(score):
    if score > 30:
        return "主力強力買進"
    elif score > 10:
        return "主力溫和買進"
    elif score > -10:
        return "散戶盤整"
    elif score > -30:
        return "主力溫和賣出"
    else:
        return "主力強力賣出"


def _parse_list(val):
    """Parse CSV list string like '[1,2,3]' → [1,2,3]"""
    try:
        if isinstance(val, str) and val.startswith('['):
            return [float(x.strip()) for x in val.strip('[]').split(',') if x.strip()]
    except Exception:
        pass
    return []


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
        stocks = get_active_stocks()
        data = {}
        for sid in stocks:
            path = f"{sid}.csv"
            try:
                mt = os.path.getmtime(path) if os.path.exists(path) else 0
                if mt != last_mtimes.get(sid, 0):
                    last_mtimes[sid] = mt
            except OSError:
                pass
            rec = read_latest_csv(sid)
            d = rec if rec else _empty_card(sid)
            d["_records"] = _recent_rows_api(sid)
            data[sid] = d
        if data:
            sse_queue.put(data)
        time.sleep(DATA_INTERVAL)


def _recent_rows_api(stock_id: str, n: int = 5) -> list:
    rows = read_recent_rows(stock_id, n)
    records = []
    for r in rows:
        records.append({
            "time": r.get("timestamp", "")[-8:],
            "price": _normalize_price(_num(r, "close_price")),
            "vol": _num(r, "deal_volume", int) or 0,
            "in_vol": _num(r, "total_in_volume", int) or 0,
            "out_vol": _num(r, "total_out_volume", int) or 0,
            "amt": _num(r, "deal_amount") or 0,
        })
    return records


def read_recent_rows(stock_id: str, n: int = 5) -> list:
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def _empty_card(stock_id: str) -> dict:
    return {"stock_id": stock_id, "stock_name": get_stock_name(stock_id),
            "close_price": None, "open_price": None, "timestamp": "",
            "high_price": None, "low_price": None, "price_diff": None,
            "deal_volume": 0, "deal_amount": None, "trade_count": 0,
            "total_in_volume": 0, "total_out_volume": 0, "estimated_day_volume": 0,
            "pct_of_yesterday_avg": None, "ma5": None, "ma10": None,
            "stock_type": "unknown", "participation_score": None,
            "participation_label": "等待資料",
            "buy_prices": [], "buy_volumes": [], "sell_prices": [], "sell_volumes": [],
            "buy_total_volume": 0, "sell_total_volume": 0, "buy_sell_imbalance": 0}


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
    for sid in get_active_stocks():
        rec = read_latest_csv(sid)
        result[sid] = rec if rec else _empty_card(sid)
    return jsonify(result)


@app.route("/api/records")
def api_records():
    result = {}
    for sid in get_active_stocks():
        rows = read_recent_rows(sid, 5)
        records = []
        for r in rows:
            records.append({
                "time": r.get("timestamp", "")[-8:],
                "price": _num(r, "close_price"),
                "vol": _num(r, "deal_volume", int) or 0,
                "in_vol": _num(r, "total_in_volume", int) or 0,
                "out_vol": _num(r, "total_out_volume", int) or 0,
                "amt": _num(r, "deal_amount") or 0,
            })
        result[sid] = records
    return jsonify(result)


@app.route("/api/watchlists")
def api_watchlists():
    wl = load_watchlists()
    return jsonify({
        "watchlists": list(wl.keys()),
        "active": _active_watchlist,
    })


@app.route("/api/watchlist/<name>", methods=["POST"])
def api_switch_watchlist(name):
    global _active_watchlist
    wl = load_watchlists()
    if name in wl:
        _active_watchlist = name
        return jsonify({"ok": True, "active": name, "stocks": wl[name].get("stocks", [])})
    return jsonify({"ok": False, "error": f"自選股 '{name}' 不存在"}), 404


@app.route("/api/lookup")
def api_lookup():
    """股票代號 ↔ 公司名稱 雙向查詢。
    ?symbol=2330 → 回傳公司名稱
    ?name=台積電 → 回傳股票代號
    ?q=xxx → 自動判斷（先試代號，再試名稱）"""
    names = load_names()
    symbol = request.args.get("symbol", "")
    name = request.args.get("name", "")
    q = request.args.get("q", "")

    if symbol:
        result = names.get(symbol.strip())
        return jsonify({"query": symbol, "result": result, "type": "symbol_to_name"})
    if name:
        name = name.strip()
        match = next((sid for sid, cname in names.items() if cname == name), None)
        return jsonify({"query": name, "result": match, "type": "name_to_symbol"})
    if q:
        q = q.strip()
        if q in names:
            return jsonify({"query": q, "result": names[q], "type": "symbol_to_name"})
        match = next((sid for sid, cname in names.items() if cname == q), None)
        if match:
            return jsonify({"query": q, "result": match, "type": "name_to_symbol"})
        if q.isdigit() and len(q) == 4:
            return jsonify({"query": q, "result": None, "type": "symbol_to_name",
                            "hint": f"'{q}' 不在 stock_names.json 中"})
        return jsonify({"query": q, "result": None, "type": "unknown",
                        "hint": f"找不到 '{q}'，請確認股票代號或公司名稱"})
    return jsonify({"error": "請提供 symbol= 或 name= 或 q= 查詢參數"}), 400


@app.route("/api/options")
def api_options():
    """Put/Call 合理價分析。查詢參數: S(現貨價), K(履約價), days(到期天數),
    call(市價), put(市價), vol(波動率,預設0.25)"""
    try:
        S = float(request.args.get("S", 0))
        K = float(request.args.get("K", 0))
        days = int(request.args.get("days", 30))
        call_mkt = float(request.args.get("call", 0))
        put_mkt = float(request.args.get("put", 0))
        vol = float(request.args.get("vol", 0.25))
    except (TypeError, ValueError):
        return jsonify({"error": "無效參數"}), 400

    if S <= 0 or K <= 0:
        return jsonify({"error": "S 和 K 必須大於 0"}), 400

    pricing = OptionPricing()
    result = pricing.evaluate(S, K, days, call_mkt, put_mkt, vol)

    pcr = put_call_ratio_analysis(
        call_vol=float(request.args.get("cv", call_mkt or 1)),
        put_vol=float(request.args.get("pv", put_mkt or 1)),
        call_oi=float(request.args.get("coi", 0)) or None,
        put_oi=float(request.args.get("poi", 0)) or None,
    )

    return jsonify({
        "S": S, "K": K, "days": days,
        "fair_call": result.fair_call,
        "fair_put": result.fair_put,
        "call_premium_pct": result.call_premium_pct,
        "put_premium_pct": result.put_premium_pct,
        "call_iv": result.call_iv,
        "put_iv": result.put_iv,
        "parity_diff": result.parity_diff,
        "pcr": pcr,
    })


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
