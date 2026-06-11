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
import hedge_dashboard

app = Flask(__name__)
@app.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
hedge_dashboard.register(app)
sse_queue = queue.Queue()

WATCHLIST_PATH = "watchlist.json"
NAMES_PATH = "stock_names.json"
_active_watchlist = "自選股1"

#todo:優先權放後面,此方發簡單但無法避免新上市或下市,需要skill來避免,也許已存在,若有請用繁體紀錄使用方式於prd.md
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
DATA_INTERVAL = 0.5
SNAPSHOT_DIR = "snapshot"
HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>v2.2-0609 • Yuanta OneAPI 即時監控</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:'Microsoft YaHei',sans-serif;padding:16px}
	.stat-row{display:flex;justify-content:space-between;font-size:11px;margin-top:6px;color:#8b949e;border-top:1px solid #21262d;padding-top:4px}
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
.price.limit-up{background:#da3633;color:#fff;padding:2px 8px;border-radius:4px;display:inline-block}
.price.limit-down{background:#238636;color:#fff;padding:2px 8px;border-radius:4px;display:inline-block}
.up{color:#f85149}.down{color:#3fb950}.muted{color:#8b949e}
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
.c-recs{display:none}.c-recs.open{display:block}
.depth-table{width:100%;border-collapse:collapse;font-size:11px;margin-top:4px}
.depth-table th{color:#8b949e;font-weight:normal;text-align:right;padding:1px 4px}
.depth-table td{text-align:right;padding:1px 4px;font-variant-numeric:tabular-nums}
.depth-table .bid{color:#3fb950}.depth-table .ask{color:#f85149}
.stale{color:#f85149}.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}.status-dot.live{background:#3fb950;box-shadow:0 0 6px #3fb950}.status-dot.stale{background:#f85149;box-shadow:0 0 6px #f85149}.status-dot.dead{background:#6e7681}
</style>
</head>
<body>
<div class="header">
<h1>v2.2-0609 Yuanta OneAPI — 即時監控 <a href="/hedge" style="font-size:13px;color:#d2991d;text-decoration:none;margin-left:12px">避險</a></h1>
<div style="display:flex;gap:8px;align-items:center">
<select class="wl-select" id="wlSelect" onchange="switchWatchlist(this.value)"></select>
<input id="stockSearch" placeholder="搜尋代號或名稱..." style="padding:6px 8px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;font-size:12px;width:160px" onkeyup="if(event.key==='Enter')addStock()">
<button onclick="addStock()" style="padding:6px 12px;background:#238636;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px">+ 新增</button>
<div id="searchResults" style="position:absolute;top:40px;background:#161b22;border:1px solid #30363d;border-radius:6px;z-index:99;display:none;max-height:200px;overflow-y:auto"></div>
</div>
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
function vol(n){if(n==null||n<0)return'--';return String(Math.round(n/1000)).replace(/\B(?=(\d{3})+(?!\d))/g,',');}
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
  if(s.close_price==null) return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span><button onclick="removeStock('${s.stock_id}')" title="移除" style="float:right;background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;padding:0 4px">×</button></h2><div class="row muted">等待資料...</div>`;
  const ref = s.ref_price != null ? s.ref_price : (s.open_price != null ? s.open_price : null);
  const cls = (ref !== null && s.close_price !== null)
    ? (s.close_price > ref ? 'up' : s.close_price < ref ? 'down' : '')
    : '';
  const limitCls = s.limit_state === 'up' ? ' limit-up' : s.limit_state === 'down' ? ' limit-down' : '';
  const limitLabel=s.limit_state==='up'?' 漲停':s.limit_state==='down'?' 跌停':'';
  const chgPct=(ref !== null && s.close_price != null && ref !== 0)
    ?(((s.close_price - ref) / ref) * 100).toFixed(2):'--';
  const inRatio=(s.total_in_volume || 0)+(s.total_out_volume || 0) > 0
    ?(((s.total_in_volume || 0)/((s.total_in_volume || 0)+(s.total_out_volume || 0))) * 100).toFixed(1):50;
  const dealAmt=s.deal_amount||0, dealVol=s.deal_volume||0;
  let recs='';
  if(s._records&&s._records.length){
    recs='<table class="depth-table" style="margin-top:4px"><tr><th>時間</th><th>成交價</th><th>量(張)</th><th>內盤</th><th>外盤</th><th>金額</th></tr>';
    for(const r of s._records){
      recs+=`<tr><td>${r.time||'--'}</td><td>${fmt(r.price)}</td><td>${vol(r.vol)}</td><td>${vol(r.in_vol)}</td><td>${vol(r.out_vol)}</td><td>${(Math.max(0,r.amt)/1e4).toFixed(2)}萬</td></tr>`;
    }
    recs+='</table>';
  }
  const uid='r'+s.stock_id;
	  const recsOpen = _recsOpen ? ' open' : '';
  return `<h2>${s.stock_name||s.stock_id} <span>${s.stock_id}</span> <span>${badge(s.stock_type)}</span><button onclick="removeStock('${s.stock_id}')" title="移除" style="float:right;background:none;border:none;color:#8b949e;cursor:pointer;font-size:16px;padding:0 4px">×</button></h2>
<div class="price ${cls}${limitCls}">${fmt(s.close_price)} ${limitLabel} <span style="font-size:13px">${chgPct>0?'+'+chgPct:chgPct}%</span></div>
<div class="row"><span>開 ${fmt(s.open_price)}</span><span>高 ${fmt(s.high_price)}</span><span>低 ${fmt(s.low_price)}</span></div>
<div class="row"><span>量 ${vol(dealVol)} 張</span><span>成交筆數 ${String(s.trade_count||0).replace(/\B(?=(\d{3})+(?!\d))/g,',')}</span></div>
<div class="row"><span>內盤 ${vol(s.total_in_volume)} 張</span><span class="muted">外盤 ${vol(s.total_out_volume)} 張</span></div>
<div class="row"><span>${s.volume_label||'估日量'} ${vol(s.estimated_day_volume)} 張</span><span class="muted">${s.pct_of_yesterday_avg!=null?(s.pct_of_yesterday_avg>=0?'增':'縮')+Math.abs(s.pct_of_yesterday_avg).toFixed(1)+'%':'--'}</span></div>
<div class="row"><span>MA5 ${fmt(s.ma5)}</span><span class="muted">MA10 ${fmt(s.ma10)}</span><span>${tag(s.participation_label||'N/A')}</span></div>
<div class="row" style="font-size:11px"><span class="${s.pe_source==='forward'?'up':'muted'}" title="${s.pe_source==='forward'?'本益比使用法人預估EPS':(s.pe_source==='trailing'?'本益比使用近四季EPS':'無EPS資料')}">PE ${fmt(s.pe,1)||"--"}</span>${s.pe_revision==='up'?'<span class="up" style="font-size:9px;margin-left:2px">上修</span>':s.pe_revision==='down'?'<span class="down" style="font-size:9px;margin-left:2px">下修</span>':''}<span class="muted"> PB ${fmt(s.pb,2)||"--"} PEG ${fmt(s.peg,2)||"--"}</span></div>
<div class="bar"><div class="bar-fill" style="width:${Math.min(100,Math.max(0,inRatio))}%;background:${inRatio>55?'#3fb950':inRatio<45?'#f85149':'#6e7681'}"></div></div>
<div class="row"><span class="muted">買盤佔比 ${inRatio}%</span><span class="muted">Score: ${s.participation_score||'--'}</span></div>
<div class="stat-row"><span>${(s.timestamp||'').slice(-8)}</span><span>成交總額 ${(dealAmt/1e4).toFixed(2)}萬 / ${vol(dealVol)}張</span></div>
<div class="c-recs${recsOpen}">${recs}</div>`;
}
function render(data){
  const g=document.getElementById('grid'), active=new Set(Object.keys(data)), now=Date.now();
  for(const id of Object.keys(cards)){if(!active.has(id)){cards[id].remove();delete cards[id];}}
  for(const [id,s] of Object.entries(data)){
    let el=cards[id];
    if(!el){el=document.createElement('div');el.className='card';cards[id]=el;g.appendChild(el);}
    const h=cardHTML(s);if(el._h!==h){el.innerHTML=h;el._h=h;}
    // 資料滯後 > 30 秒 → 邊框變紅警告
    const ts=s.timestamp;let stale=false;
    if(ts){const parts=ts.split(' ');if(parts.length>=2){const t=parts[1].split(':');const sec=now/1000-((+t[0])*3600+(+t[1])*60+(+t[2]));if(sec>30)stale=true;}}
    el.style.borderColor=stale?'#f85149':'#30363d';
  }
  for(const[id,el] of Object.entries(cards)){
    const r=el.querySelector('.c-recs');if(r)r.classList.toggle('open',_recsOpen);
  }
}
function summary(data){
  let totalVol=0,totalIn=0,totalOut=0,up=0,down=0;const entries=Object.entries(data);
  for(const[,s] of entries){
    totalVol += (s.deal_volume||0);
    totalIn += (s.total_in_volume||0);
    totalOut += (s.total_out_volume||0);
    if (s.close_price != null && s.open_price != null) {
      if (s.close_price > s.open_price) up++;
      else if (s.close_price < s.open_price) down++;
    }
  }
  const inPct=totalIn+totalOut>0?Math.round(totalIn/(totalIn+totalOut)*100):50;
  const bar=document.getElementById('summary');
  if(!bar._built){bar.innerHTML='<div class="summary-item"><span class="s-cnt"></span> <span class="s-updn"></span></div><div class="summary-item">總量 <span class="num s-tvol"></span></div><div class="summary-item">內盤佔比 <span class="num s-inpct"></span></div>';bar._built=true;}
  setText(bar.querySelector('.s-cnt'),'監控 '+entries.length+' 檔');
  setText(bar.querySelector('.s-updn'),up+'↑ '+down+'↓');
  setText(bar.querySelector('.s-tvol'),String(Math.round(totalVol/1000)).replace(/\B(?=(\d{3})+(?!\d))/g,',')+' 張');
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
    const r=el.querySelector('.c-recs');if(r)r.classList.toggle('open',_recsOpen);
  }
}
const es=new EventSource('/stream');
let _lastUpdate=Date.now(),_staleCheck=null;
es.onopen=function(){statusEl.innerHTML='<span class="status-dot live"></span>SSE 已連線'};
es.onerror=function(){statusEl.innerHTML='<span class="status-dot dead"></span>SSE 斷線，重新連線中...'};
es.onmessage=function(e){const d=JSON.parse(e.data);render(d);summary(d);_lastUpdate=Date.now();statusEl.innerHTML='<span class="status-dot live"></span>更新 '+new Date().toLocaleTimeString()};
_staleCheck=setInterval(function(){
  const sec=Math.round((Date.now()-_lastUpdate)/1000);
  if(sec>10)statusEl.innerHTML='<span class="status-dot stale"></span>資料滯後 '+sec+'秒';
},2000);

async function addStock(){
  const inp=document.getElementById('stockSearch'),q=inp.value.trim();
  if(!q)return;
  const r=await fetch('/api/watchlist/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock_id:q})});
  const d=await r.json();
  if(d.ok){inp.value='';location.reload();}
  else alert(d.error||'新增失敗');
}
async function removeStock(sid){
  if(!confirm(`確定要移除 ${sid} 嗎？`))return;
  const r=await fetch('/api/watchlist/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock_id:sid})});
  const d=await r.json();
  if(d.ok)location.reload();
  else alert(d.error||'移除失敗');
}
let _searchTimer=null;
document.getElementById('stockSearch').addEventListener('input',function(){
  clearTimeout(_searchTimer);
  const q=this.value.trim();
  if(!q){document.getElementById('searchResults').style.display='none';return;}
  _searchTimer=setTimeout(async()=>{
    const r=await fetch('/api/stock/search?q='+encodeURIComponent(q));
    const d=await r.json();
    const div=document.getElementById('searchResults');
    if(!d.results.length){div.style.display='none';return;}
    div.innerHTML=d.results.map(s=>`<div style="padding:4px 8px;cursor:pointer;font-size:12px" onmouseover="this.style.background='#21262d'" onmouseout="this.style.background=''" onclick="document.getElementById('stockSearch').value='${s.symbol}';document.getElementById('searchResults').style.display='none';addStock()">${s.symbol} ${s.name}</div>`).join('');
    div.style.display='block';
  },200);
});
document.addEventListener('click',function(e){if(!e.target.closest('#stockSearch')&&!e.target.closest('#searchResults'))document.getElementById('searchResults').style.display='none';});

</script>
</body>
</html>"""


def read_snapshot(stock_id: str) -> dict | None:
    """從 snapshot/{stock_id}.json 讀取最新狀態（0.5 秒更新）。"""
    path = os.path.join(SNAPSHOT_DIR, f"{stock_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        # 轉換為 dashboard 相容格式（與 read_latest_csv 回傳格式一致）
        d = {
            "stock_id": snap.get("stock_id", stock_id),
            "stock_name": get_stock_name(stock_id),
            "buy_prices": snap.get("buy_prices", []),
            "buy_volumes": snap.get("buy_volumes", []),
            "sell_prices": snap.get("sell_prices", []),
            "sell_volumes": snap.get("sell_volumes", []),
            "buy_total_volume": max(0, snap.get("buy_total_volume", 0) or 0),
            "sell_total_volume": max(0, snap.get("sell_total_volume", 0) or 0),
            "buy_sell_imbalance": snap.get("buy_sell_imbalance"),
            # 優先使用累積值（API 提供的總成交金額/總量），區間值作為降級
            "deal_amount": snap.get("cumulative_deal_amount") if snap.get("cumulative_deal_amount") is not None else snap.get("deal_amount"),
            "close_price": snap.get("close_price"),
            "open_price": snap.get("open_price"),
            "high_price": snap.get("high_price"),
            "low_price": snap.get("low_price"),
            "price_diff": snap.get("price_diff"),
            "deal_volume": snap.get("cumulative_deal_volume") if snap.get("cumulative_deal_volume") is not None else max(0, snap.get("deal_volume", 0) or 0),
            "trade_count": snap.get("trade_count"),
            "total_in_volume": max(0, snap.get("total_in_volume", 0) or 0),
            "total_out_volume": max(0, snap.get("total_out_volume", 0) or 0),
            "estimated_day_volume": max(0, snap.get("estimated_day_volume", 0) or 0),
            "volume_label": snap.get("volume_label", "估日量"),
            "pct_of_yesterday_avg": snap.get("pct_of_yesterday_avg"),
            "ma5": snap.get("ma5"),
            "ma10": snap.get("ma10"),
            "stock_type": snap.get("stock_type", ""),
            "timestamp": snap.get("timestamp", ""),
            "participation_score": snap.get("participation_score"),
            "participation_label": snap.get("participation_label", ""),
            # 財務數據 (PE/PB/PEG)
            "pe": None, "pb": None, "peg": None, "peg_note": "",
            "ref_price": _get_ref_price(stock_id, snap.get("open_price")),
            "limit_state": _calc_limit_state(snap.get("close_price"), stock_id),
            "_records": snap.get("records", []),
        }
        # 盤後若 snapshot records 為空，從 CSV 讀取完整紀錄
        if not d["_records"]:
            from datetime import datetime as _dt
            if _dt.now().hour >= 14:
                d["_records"] = _recent_rows_api(stock_id, n=10)
        # 盤後用 @stockID.csv 覆蓋
        actual_vol, day_info = _get_actual_day_volume(stock_id)
        if actual_vol is not None:
            d["estimated_day_volume"] = actual_vol
            d["volume_label"] = "盤後總量"
        if day_info is not None:
            if day_info.get("close") is not None:
                d["close_price"] = day_info["close"]
            if day_info.get("open") is not None:
                d["open_price"] = day_info["open"]
            if day_info.get("high") is not None:
                d["high_price"] = day_info["high"]
            if day_info.get("low") is not None:
                d["low_price"] = day_info["low"]
            if d["close_price"] is not None and d["open_price"] is not None:
                d["price_diff"] = round(d["close_price"] - d["open_price"], 2)
            d["limit_state"] = _calc_limit_state(d["close_price"], stock_id)
        # PE/PB/PEG from live price + static fundamentals（在 close_price 覆蓋後計算）
        fund = _FUND.get(stock_id)
        d["pe"], d["pb"], d["peg"], d["peg_note"], d["pe_source"], d["pe_revision"] = _compute_pe_pb_peg(d.get("close_price"), fund)
        # 盤後用 actual_vol 覆蓋 deal_volume/deal_amount
        if actual_vol and actual_vol > (d.get("deal_volume") or 0):
            d["deal_volume"] = actual_vol
            d["deal_amount"] = int(actual_vol * d["close_price"]) if d.get("close_price") else None
        # 補救 stock_type
        if not d["stock_type"] or d["stock_type"] == "unknown":
            d["stock_type"] = _detect_stock_type(stock_id, d["close_price"])
        # 補救 participation
        if d["participation_label"] in ("", "N/A", "等待資料") and d["total_in_volume"] + d["total_out_volume"] > 0:
            d["participation_score"] = round((d["total_in_volume"] - d["total_out_volume"]) / (d["total_in_volume"] + d["total_out_volume"]) * 50, 1)
            d["participation_label"] = _score_to_label(d["participation_score"])
        return d
    except Exception:
        return None


def read_latest_csv(stock_id: str) -> dict | None:
    """讀取最新 CSV 資料（作為 snapshot 不存在時的降級方案）。"""
    # 優先讀取 snapshot（0.5 秒更新，1KB 小檔案）
    snap = read_snapshot(stock_id)
    if snap is not None and snap.get("close_price") is not None:
        return snap
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
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
        # 若隱含成交價不合理 (>20000 元/股)，視為 API 原始整數金額，正規化
        if deal_amount is not None and deal_volume and deal_volume > 0:
            implied = deal_amount / deal_volume
            if implied > 20000:
                deal_amount = round(deal_amount / 10000, 0)
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
        def _normalize_volume(val):
            if val is None:
                return None
            try:
                return max(0, int(val))
            except (TypeError, ValueError):
                return None

        # 累積成交總額/總量（CSV 中有 cumulative_ 前綴的欄位）
        cum_vol = _normalize_volume(_num(row, "cumulative_volume", int))
        cum_amt = None
        if cum_vol and close_price:
            cum_amt = int(cum_vol * close_price)

        d = {
            "stock_id": row.get("stock_id", stock_id),
            "stock_name": get_stock_name(stock_id),
            "buy_prices": buy_prices,
            "buy_volumes": buy_volumes,
            "sell_prices": sell_prices,
            "sell_volumes": sell_volumes,
            "buy_total_volume": max(0, buy_total_volume),
            "sell_total_volume": max(0, sell_total_volume),
            "buy_sell_imbalance": buy_sell_imbalance,
            # 優先使用累積值，區間值為降級
            "deal_amount": cum_amt if cum_amt else deal_amount,
            "close_price": close_price,
            "open_price": open_price,
            "high_price": _normalize_price(_num(row, "high_price")),
            "low_price": _normalize_price(_num(row, "low_price")),
            "price_diff": price_diff,
            "deal_volume": cum_vol if cum_vol else _normalize_volume(deal_volume),
            "trade_count": _num(row, "trade_count", int),
            "total_in_volume": _normalize_volume(_num(row, "total_in_volume", int)),
            "total_out_volume": _normalize_volume(_num(row, "total_out_volume", int)),
            "estimated_day_volume": _normalize_volume(_num(row, "estimated_day_volume", int)),
            "volume_label": row.get("volume_label", "估日量"),
            "pct_of_yesterday_avg": pct_of_yesterday_avg,
            "ma5": _normalize_price(_num(row, "ma5")),
            "ma10": _normalize_price(_num(row, "ma10")),
            "stock_type": stock_type,
            "timestamp": row.get("timestamp", ""),
            "participation_score": participation_score,
            "participation_label": participation_label if participation_label not in ("", "N/A", "等待資料") else "等待資料",
            "ref_price": _get_ref_price(stock_id, open_price),
            "limit_state": _calc_limit_state(close_price, stock_id),
        }
        # 盤後 (14:30+) 用 @stockID.csv 的真實數據覆蓋估算值
        actual_vol, day_info = _get_actual_day_volume(stock_id)
        if actual_vol is not None:
            d["estimated_day_volume"] = actual_vol
            d["volume_label"] = "盤後總量"
        if day_info is not None:
            if day_info.get("close") is not None:
                d["close_price"] = day_info["close"]
            if day_info.get("open") is not None:
                d["open_price"] = day_info["open"]
            if day_info.get("high") is not None:
                d["high_price"] = day_info["high"]
            if day_info.get("low") is not None:
                d["low_price"] = day_info["low"]
            # 重算漲跌價差與漲跌停狀態
            if d["close_price"] is not None and d["open_price"] is not None:
                d["price_diff"] = round(d["close_price"] - d["open_price"], 2)
            d["limit_state"] = _calc_limit_state(d["close_price"], stock_id)
        # PE/PB/PEG from live price + static fundamentals（在 close_price 覆蓋後計算）
        fund = _FUND.get(stock_id)
        d["pe"], d["pb"], d["peg"], d["peg_note"], d["pe_source"], d["pe_revision"] = _compute_pe_pb_peg(d.get("close_price"), fund)
        # 盤後用 actual_vol 覆蓋 deal_volume/deal_amount
        if actual_vol and actual_vol > (d.get("deal_volume") or 0):
            d["deal_volume"] = actual_vol
            d["deal_amount"] = int(actual_vol * d["close_price"]) if d.get("close_price") else None
        # MA backup: keep last known good value
        for key in ("ma5", "ma10"):
            if d[key] is None:
                d[key] = _LAST_KNOWN.get(stock_id, {}).get(key)
        return d
    except Exception:
        return None

#val必須為無符號,避免負值影響計算,目前方法存在瑕疵,為 bug 原因之一需修正
def _normalize_price(val):
    """將可能為 API 原始整數的價格正規化為 TWD。
    台灣個股價格合理範圍 1~15000，若超過 100000 視為原始整數 (/10000)；
    0 或負值視為無效，回傳 None。"""
    if val is None:
        return None
    try:
        if val <= 0:
            return None
    except TypeError:
        return None
    if abs(val) >= 100000:
        return round(val / 10000, 2)
    return val


def _load_stock_ref() -> dict:
    """從 stock_ref.json 載入 API 查詢的昨收/漲停/跌停參考價。建議程式入口先檢查自選股的ref_price是否存在昨收,不存在則使用此工具更新方法"""
    path = "stock_ref.json"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_ref_price(stock_id: str, fallback_open=None):
    """取得漲跌顏色基準價（昨收價），含多重降級。
    優先: stock_ref.json (API) → @stockID.csv → open_price。"""
    # 1) API 查詢的昨收價
    ref = _load_stock_ref()
    entry = ref.get(stock_id, {})
    yst = _normalize_price(entry.get("yst_price"))
    if yst is not None:
        return yst
    # 2) @stockID.csv 最後一筆收盤價 (支援中英文欄位名),若檔案時間屬性不合理就可很快判斷,需要外部工具修護正確資料.建議程式入口先檢查
    path = f"@{stock_id}.csv"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
            if rows:
                yst = _normalize_price(_num(rows[-1], "收盤價") or _num(rows[-1], "close_price"))
                if yst is not None:
                    return yst
        except Exception:
            pass
    # 3) 今日開盤價
    return fallback_open


def _get_limit_prices(stock_id: str):
    """取得漲停價/跌停價。
    優先: stock_ref.json API 提供的 up_price/down_price（已考量除權息調整）
    降級: 昨收價 ×1.10 / ×0.90（標準 10%）
    回傳 (up_price, down_price) 或 (None, None)。"""
    yst = _get_ref_price(stock_id)
    ref = _load_stock_ref()
    entry = ref.get(stock_id, {})
    api_up = _normalize_price(entry.get("up_price"))
    api_down = _normalize_price(entry.get("down_price"))
    # 驗證 API 值合理性：漲停 > 昨收 > 跌停
    if api_up is not None and api_down is not None and yst is not None:
        if api_up > yst > api_down:
            return api_up, api_down
    # 降級：直接用昨收計算 ±10%
    if yst is not None and yst > 0:
        return round(yst * 1.10, 2), round(yst * 0.90, 2)
    return None, None


def _calc_limit_state(close_price, stock_id):
    """判斷是否漲跌停。"""
    if close_price is None:
        return None
    up_price, down_price = _get_limit_prices(stock_id)
    if up_price is not None and close_price >= up_price:
        return 'up'
    if down_price is not None and close_price <= down_price:
        return 'down'
    return None

# 市值分類快取（從 market_cap.json 載入）
_market_cap_cache = None
_market_cap_cache_time = 0


def _load_market_cap():
    """載入市值排名資料（含 1 小時快取）。"""
    global _market_cap_cache, _market_cap_cache_time
    now = time.time()
    if _market_cap_cache is not None and now - _market_cap_cache_time < 3600:
        return _market_cap_cache
    path = "market_cap.json"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                _market_cap_cache = json.load(f)
            _market_cap_cache_time = now
            return _market_cap_cache
        except Exception:
            pass
    return None


_fin_cache = None
_fin_cache_time = 0


def _load_financials():
    """載入財務數據（優先 analyst_eps.json → 降級 stock_financials.json）。
    含 1 小時快取。"""
    global _fin_cache, _fin_cache_time
    now = time.time()
    if _fin_cache is not None and now - _fin_cache_time < 3600:
        return _fin_cache

    result = {}
    # 1) 優先: analyst_eps.json (法人預估共識)
    analyst_path = "analyst_eps.json"
    if os.path.exists(analyst_path):
        try:
            with open(analyst_path, encoding="utf-8") as f:
                analyst = json.load(f)
            for code, s in analyst.get("stocks", {}).items():
                peg_info = s.get("peg", {}) or {}
                result[code] = {
                    "pe": peg_info.get("forward_pe"),
                    "pb": None,
                    "peg": peg_info.get("peg"),
                    "peg_note": f"法人預估EPS={s.get('consensus_eps','?')} ({s.get('method','?')})"
                }
        except Exception:
            pass

    # 2) 降級: stock_financials.json (近四季 EPS)
    fin_path = "stock_financials.json"
    if os.path.exists(fin_path):
        try:
            with open(fin_path, encoding="utf-8") as f:
                fin = json.load(f)
            for code, s in fin.get("stocks", {}).items():
                if code not in result or result[code].get("pe") is None:
                    result[code] = {
                        "pe": s.get("pe"),
                        "pb": s.get("pb"),
                        "peg": s.get("peg"),
                        "peg_note": s.get("peg_note", ""),
                    }
        except Exception:
            pass

    # 3) 補 market_cap.json 的 PE/PB
    mcap = _load_market_cap()
    if mcap:
        for code, s in mcap.get("stocks", {}).items():
            if code in result:
                if result[code].get("pe") is None:
                    result[code]["pe"] = s.get("pe")
                if result[code].get("pb") is None:
                    result[code]["pb"] = s.get("pb")

    _fin_cache = result
    _fin_cache_time = now
    return result

def _load_fundamentals():
    """Load fundamentals.json once; PE/PB/PEG computed from live price.
    PE = close / eps_ttm ; PB = close / bps ; PEG = (close/forward_eps) / |growth|
    """
    path = "fundamentals.json"
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("stocks", {})
        except Exception:
            pass
    return {}

def _compute_pe_pb_peg(close_price, fund):
    """Compute PE/PB/PEG from live close_price + static fundamentals.
    Returns (pe, pb, peg, peg_note, pe_source, revision).
    pe_source: 'forward' | 'trailing' | None
    revision: 'up' (fwd_eps > ttm_eps) | 'down' (fwd_eps < ttm_eps) | None
    PE prefers forward_eps if available, falls back to eps_ttm."""
    if not fund or close_price is None:
        return None, None, None, "", None, None
    eps = fund.get("eps_ttm")
    bps = fund.get("bps")
    growth = fund.get("eps_growth_pct")
    fwd_eps = fund.get("forward_eps")

    # PE: prefer forward_eps (analyst estimate), fallback to trailing eps_ttm
    forward_pe = round(close_price / fwd_eps, 2) if fwd_eps and fwd_eps > 0 else None
    trailing_pe = round(close_price / eps, 2) if eps and eps > 0 else None
    pe = forward_pe if forward_pe is not None else trailing_pe
    pe_source = 'forward' if forward_pe is not None else ('trailing' if trailing_pe is not None else None)

    # Revision: compare forward_eps vs eps_ttm (proxy for analyst revision direction)
    revision = None
    if fwd_eps and eps and eps > 0:
        if fwd_eps > eps:
            revision = 'up'
        elif fwd_eps < eps:
            revision = 'down'

    pb = round(close_price / bps, 2) if bps and bps > 0 else None

    peg = None
    note = fund.get("note", "")
    use_eps = fwd_eps if fwd_eps else eps

    if pe and growth and abs(growth) > 0.1 and use_eps:
        peg = round(pe / abs(growth), 2)
        src = 'forward' if fwd_eps else 'ttm'
        note = f'{src}EPS={use_eps} | {note}'
    elif use_eps and use_eps > 0:
        src = 'forward' if fwd_eps else 'ttm'
        note = f'{src}EPS={use_eps} | no PEG'

    return pe, pb, peg, note, pe_source, revision

_LAST_KNOWN = {}
_FUND = _load_fundamentals()

def _detect_stock_type(stock_id: str, price=None) -> str:
    """依市值排名分類：大型/中型/小型。
    優先使用 market_cap.json（每月更新），降級使用內建 0050 清單。"""
    # 1) market_cap.json 排名
    mcap = _load_market_cap()
    if mcap and stock_id in mcap.get("stocks", {}):
        tier = mcap["stocks"][stock_id].get("tier", "")
        if tier in ("large_cap", "mid_cap", "small_cap"):
            return tier
    # 2) 降級：內建 0050 成分股清單
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
    last_snap_mtimes = {}
    while True:
        stocks = get_active_stocks()
        data = {}
        for sid in stocks:
            # 檢查 snapshot 是否有更新
            snap_path = os.path.join(SNAPSHOT_DIR, f"{sid}.json")
            snap_mt = os.path.getmtime(snap_path) if os.path.exists(snap_path) else 0
            need_refresh = snap_mt != last_snap_mtimes.get(sid, 0)
            if need_refresh:
                last_snap_mtimes[sid] = snap_mt

            rec = read_latest_csv(sid)
            d = rec if rec else _empty_card(sid)
            # 使用 snapshot 內建的 records；若無則降級讀 CSV
            if not d.get("_records"):
                d["_records"] = _recent_rows_api(sid)
            data[sid] = d
        if data:
            sse_queue.put(data)
        time.sleep(DATA_INTERVAL)


def _recent_rows_api(stock_id: str, n: int = 5) -> list:
    # 往前多讀一些，確保低量股也能湊滿 n 列有成交量的資料
    rows = read_recent_rows(stock_id, max(n * 6, 30))
    records = []
    for r in rows:
        price = _normalize_price(_num(r, "close_price"))
        vol = max(0, _num(r, "deal_volume", int) or 0)
        # int32 溢位防護: 負值轉無號 (> 2^31 視為溢位)
        if vol < 0:
            vol = vol + 0x100000000
        amt = _num(r, "deal_amount") or 0
        if amt < 0:
            amt = amt + 0x100000000
        if amt > 0 and vol > 0 and amt / vol > 20000:
            amt = round(amt / 10000, 0)
        in_vol = max(0, _num(r, "total_in_volume", int) or 0)
        out_vol = max(0, _num(r, "total_out_volume", int) or 0)
        if in_vol < 0:
            in_vol = in_vol + 0x100000000
        if out_vol < 0:
            out_vol = out_vol + 0x100000000
        # 跳過完全無成交量的列（內外盤區間 delta 為 0）
        if vol <= 0 and in_vol <= 0 and out_vol <= 0:
            continue
        records.append({
            "time": r.get("timestamp", "")[-8:],
            "price": price,
            "vol": vol,
            "in_vol": in_vol,
            "out_vol": out_vol,
            "amt": max(0, amt),
        })
    return records[-n:] if len(records) > n else records  # 不足 n 列就顯示實際有的


def read_recent_rows(stock_id: str, n: int = 5) -> list:
    path = f"{stock_id}.csv"
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def _get_actual_day_volume(stock_id: str):
    """盤後從 @stockID.csv 讀取當日實際總量與收盤價，用於覆蓋 5 秒 CSV 的估算值。"""
    from datetime import datetime
    now = datetime.now()
    if now.hour < 14 or (now.hour == 14 and now.minute < 30):
        return None, None
    path = f"@{stock_id}.csv"
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        today = now.strftime("%Y%m%d")
        for r in reversed(rows):
            if r.get("日期", "") == today or r.get("date", "") == today:
                vol = _num(r, "成交股數") or _num(r, "total_volume")
                vol = int(vol) if vol is not None and vol > 0 else None
                close = _normalize_price(_num(r, "收盤價") or _num(r, "close_price"))
                open_p = _normalize_price(_num(r, "開盤價") or _num(r, "open_price"))
                high_p = _normalize_price(_num(r, "最高價") or _num(r, "high_price"))
                low_p = _normalize_price(_num(r, "最低價") or _num(r, "low_price"))
                day_info = {
                    "vol": vol,
                    "close": close, "open": open_p,
                    "high": high_p, "low": low_p,
                }
                return vol, day_info
        return None, None
    except Exception:
        return None, None


def _empty_card(stock_id: str) -> dict:
    return {"stock_id": stock_id, "stock_name": get_stock_name(stock_id),
            "close_price": None, "open_price": None, "timestamp": "",
            "high_price": None, "low_price": None, "price_diff": None,
            "deal_volume": 0, "deal_amount": None, "trade_count": 0,
            "total_in_volume": 0, "total_out_volume": 0, "estimated_day_volume": 0,
            "volume_label": "盤前預估量",
            "pct_of_yesterday_avg": None, "ma5": None, "ma10": None,
            "stock_type": "unknown", "participation_score": None, "pe_source": None, "pe_revision": None,
            "participation_label": "等待資料",
            "buy_prices": [], "buy_volumes": [], "sell_prices": [], "sell_volumes": [],
            "buy_total_volume": 0, "sell_total_volume": 0, "buy_sell_imbalance": 0,
            "ref_price": None, "limit_state": None}


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
            price = _normalize_price(_num(r, "close_price"))
            vol = max(0, _num(r, "deal_volume", int) or 0)
            amt = _num(r, "deal_amount") or 0
            if amt > 0 and vol > 0 and amt / vol > 20000:
                amt = round(amt / 10000, 0)
            records.append({
                "time": r.get("timestamp", "")[-8:],
                "price": price,
                "vol": vol,
                "in_vol": max(0, _num(r, "total_in_volume", int) or 0),
                "out_vol": max(0, _num(r, "total_out_volume", int) or 0),
                "amt": max(0, amt),
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


@app.route("/api/watchlist/add", methods=["POST"])
def api_watchlist_add():
    """新增股票到目前自選股，同步寫入 watchlist.json。"""
    data = request.get_json(silent=True) or {}
    stock_id = str(data.get("stock_id", "")).strip()
    if not stock_id or len(stock_id) < 4 or len(stock_id) > 6:
        return jsonify({"ok": False, "error": "請提供有效的 4-6 碼股票代號"}), 400
    # alphanumeric allowed (warrants/ETFs may contain letters e.g. 00980A)
    if not all(c.isdigit() or c.isalpha() for c in stock_id):
        return jsonify({"ok": False, "error": "股票代號僅接受英數字"}), 400

    wl = load_watchlists()
    entry = wl.get(_active_watchlist, wl.get("自選股1", {"stocks": [], "futures": []}))
    stocks = entry.get("stocks", [])
    if stock_id in stocks:
        return jsonify({"ok": False, "error": f"{stock_id} 已在自選股中"})

    stocks.append(stock_id)
    entry["stocks"] = stocks
    wl[_active_watchlist] = entry
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)

    # 嘗試為新股票取得昨日資料
    _fetch_new_stock_data(stock_id)

    # 更新全局股票清單
    global STOCKS
    STOCKS = get_active_stocks()
    return jsonify({"ok": True, "added": stock_id, "stocks": stocks,
                    "name": get_stock_name(stock_id)})


@app.route("/api/watchlist/remove", methods=["POST"])
def api_watchlist_remove():
    """從目前自選股移除股票，同步寫入 watchlist.json。"""
    data = request.get_json(silent=True) or {}
    stock_id = str(data.get("stock_id", "")).strip()

    wl = load_watchlists()
    entry = wl.get(_active_watchlist, wl.get("自選股1", {"stocks": [], "futures": []}))
    stocks = entry.get("stocks", [])
    if stock_id not in stocks:
        return jsonify({"ok": False, "error": f"{stock_id} 不在自選股中"})

    stocks.remove(stock_id)
    entry["stocks"] = stocks
    wl[_active_watchlist] = entry
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)

    global STOCKS
    STOCKS = get_active_stocks()
    return jsonify({"ok": True, "removed": stock_id, "stocks": stocks})


@app.route("/api/stock/search")
def api_stock_search():
    """模糊搜尋股票（代號 or 名稱），回傳前 20 筆。"""
    q = (request.args.get("q", "")).strip()
    if not q:
        return jsonify({"results": []})
    names = load_names()
    results = []
    q_lower = q.lower()
    for sid, cname in names.items():
        if q in sid or q_lower in cname.lower():
            results.append({"symbol": sid, "name": cname})
        if len(results) >= 20:
            break
    return jsonify({"results": results})


def _fetch_new_stock_data(stock_id: str):
    """為新加入的自選股取得昨日收盤資料、參考價，並在 fundamentals.json 建立佔位。"""
    import subprocess, sys
    # 1. fundamentals.json 補佔位（避免 PE/PB/PEG 永遠 --）
    _ensure_fund_placeholder(stock_id)
    try:
        result = subprocess.run(
            [sys.executable, "fetch_daily_close.py", "--stocks", stock_id, "--compare-only"],
            capture_output=True, text=True, timeout=60,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if "無異常" not in result.stdout:
            subprocess.run(
                [sys.executable, "fetch_daily_close.py", "--stocks", stock_id],
                capture_output=True, text=True, timeout=60,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
    except Exception:
        pass


def _ensure_fund_placeholder(stock_id: str):
    """在 fundamentals.json 中加入新股票的佔位條目（若不存在），並重載 _FUND。"""
    global _FUND
    fund_path = "fundamentals.json"
    try:
        import json as _json
        if os.path.exists(fund_path):
            with open(fund_path, "r", encoding="utf-8") as f:
                data = _json.load(f)
        else:
            data = {"updated": "", "stocks": {}}
        if stock_id not in data.get("stocks", {}):
            data.setdefault("stocks", {})[stock_id] = {
                "name": get_stock_name(stock_id),
                "eps_ttm": None, "bps": None, "eps_growth_pct": None,
                "forward_eps": None, "note": "new_stock_placeholder"
            }
            with open(fund_path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            # 重載 _FUND 讓立即生效
            _FUND = data.get("stocks", {})
    except Exception:
        pass


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
