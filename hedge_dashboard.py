"""避險儀表板 — 期貨/現貨基差監控 + 避險進場訊號。
獨立 Flask Blueprint，掛載於 web_dashboard.py。
Usage: 直接存取 http://localhost:5000/hedge

功能:
  1. TXF/TXFPM1 台指期貨 vs 加權指數現貨基差
  2. 理論期貨價 (持有成本模型) + 偏離度
  3. 動態避險門檻 (歷史基差標準差 × 1.5)
  4. 個股期貨避險 (依自選股對應)
  5. 大戶動向 (前5/前10大交易人未平倉淨部位)
"""
import csv
import json
import os
import ssl
import time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request

from flask import Blueprint, render_template_string, jsonify

# ---- Blueprint ----
hedge_bp = Blueprint("hedge", __name__, url_prefix="/hedge")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")
STOCK_REF_PATH = os.path.join(BASE_DIR, "stock_ref.json")


# ---- 工具函數 ----

def _np(val):
    """正規化價格：>100000 → /10000"""
    if val is None:
        return None
    try:
        v = float(val)
        return round(v / 10000.0) if abs(v) > 100000 else round(v, 2)
    except (ValueError, TypeError):
        return None


def _read_snapshot(code):
    """讀取 snapshot/{code}.json"""
    path = os.path.join(BASE_DIR, "snapshot", f"{code}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_last_csv_rows(code, n=60):
    """讀取 CSV 最後 N 列，用於計算歷史基差。"""
    path = os.path.join(BASE_DIR, f"{code}.csv")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        return rows[-n:]
    except Exception:
        return []


def get_watchlist_stocks():
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("stocks", [])
    except Exception:
        return []


def get_watchlist_futures():
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            config = json.load(f)
        return config.get("自選股1", {}).get("futures", [])
    except Exception:
        return []


# ---- 加權指數估算 ----
# API 可能直接推送加權指數，若無則以 0050 或主要權值股加權估算
# 此處使用簡化版：以 2330 台積電價格 × 權重係數 估算現貨指數水位
# 正式版需訂閱加權指數代碼 (MarketNo=1, Code="Y" 或類似)
_INDEX_PROXY = {
    "2330": 0.30,   # 台積電佔 ~30%
    "2317": 0.04,   # 鴻海 ~4%
    "2454": 0.04,   # 聯發科 ~4%
    "2412": 0.02,   # 中華電 ~2%
}


def estimate_weighted_index():
    """估算加權指數（以權值股價格加權）。降級方案。"""
    total_weight = 0
    weighted_sum = 0
    for code, weight in _INDEX_PROXY.items():
        snap = _read_snapshot(code)
        if snap and snap.get("close_price"):
            weighted_sum += snap["close_price"] * weight
            total_weight += weight
    if total_weight > 0:
        # 縮放到指數水準 (~23000)
        scale = 23000 / (weighted_sum / total_weight) if (weighted_sum / total_weight) > 0 else 1
        return round(weighted_sum / total_weight * scale, 2)
    return None


# ---- 理論期貨價 (Cost of Carry) ----

def theoretical_futures_price(spot, days_to_expiry, rate=0.015):
    """持有成本模型：F = S × (1 + r × t/365)。
    台灣期貨通常在到期日結算為現貨價，不考慮股利（指數期貨）。"""
    if spot is None or spot <= 0:
        return None
    return round(spot * (1 + rate * days_to_expiry / 365), 2)


def next_expiry_date():
    """計算下一個期貨到期日（每月第三個週三）。"""
    now = datetime.now()
    # 本月第三個週三
    first_day = now.replace(day=1)
    # 第一個週三
    first_wed = first_day + timedelta(days=(2 - first_day.weekday()) % 7)
    third_wed = first_wed + timedelta(days=14)
    if now > third_wed.replace(hour=13, minute=30):
        # 已過本月結算，移到下個月
        next_month = now.replace(day=28) + timedelta(days=4)
        first_day = next_month.replace(day=1)
        first_wed = first_day + timedelta(days=(2 - first_day.weekday()) % 7)
        third_wed = first_wed + timedelta(days=14)
    return third_wed


# ---- 歷史基差與動態門檻 ----

def compute_basis_stats(futures_code="TXFPM1", minutes=60):
    """從歷史 CSV 計算基差的平均與標準差（用於動態門檻）。"""
    rows = _read_last_csv_rows(futures_code, n=minutes * 12)  # ~12 rows/min
    if len(rows) < 10:
        return {"mean": 0, "std": 10, "n": 0}

    spot = estimate_weighted_index()
    if spot is None:
        # 用第一筆期貨價當基準
        return {"mean": 0, "std": 10, "n": len(rows)}

    basis_list = []
    for r in rows:
        f_price = _np(r.get("close_price"))
        if f_price and f_price > 0:
            basis = f_price - spot
            basis_list.append(basis)

    if len(basis_list) < 5:
        return {"mean": 0, "std": 10, "n": len(basis_list)}

    mean_basis = sum(basis_list) / len(basis_list)
    variance = sum((b - mean_basis) ** 2 for b in basis_list) / len(basis_list)
    std_basis = variance ** 0.5

    return {
        "mean": round(mean_basis, 2),
        "std": round(std_basis, 2),
        "n": len(basis_list),
        "recent": basis_list[-10:],
    }


# ---- 大戶動向 (TAIFEX) ----

def fetch_large_trader_position():
    """從期交所取得前5/前10大交易人未沖銷淨部位。
    資料源: https://www.taifex.com.tw/cht/3/dlOptDataDown
    回傳: {txf: {top5_long, top5_short, top10_long, top10_short}, ...}"""
    url = "https://www.taifex.com.tw/cht/3/dlOptDataDown"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # 期交所使用 POST
    now = datetime.now()
    roc_date = f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"
    data = f"down_type=1&queryDate={roc_date}".encode()

    try:
        req = Request(url, data=data, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15, context=ctx) as resp:
            html = resp.read().decode("utf-8")
    except Exception:
        return None

    # 期交所回傳 CSV 或 HTML table
    # 格式: 商品, 前五大多方, 前五大空方, 前五大淨, 前十大多方, 前十大空方, 前十大淨
    result = {}
    try:
        # 嘗試解析 CSV（期交所實際上回傳 CSV）
        lines = html.strip().split("\n")
        for line in lines:
            parts = line.replace('"', '').split(",")
            if len(parts) >= 7:
                product = parts[0].strip()
                if "臺股期貨" in product or "TXF" in product or "台股" in product:
                    result["TXF"] = {
                        "top5_long": int(parts[1]) if parts[1].isdigit() else None,
                        "top5_short": int(parts[2]) if parts[2].isdigit() else None,
                        "top5_net": int(parts[3]) if parts[3].isdigit() else None,
                        "top10_long": int(parts[4]) if parts[4].isdigit() else None,
                        "top10_short": int(parts[5]) if parts[5].isdigit() else None,
                        "top10_net": int(parts[6]) if parts[6].isdigit() else None,
                    }
        if result:
            return result
    except Exception:
        pass
    return None


# ---- 避險分析核心 ----

def analyze_hedge(futures_code="TXFPM1", spot=None):
    """綜合避險分析。"""
    snap = _read_snapshot(futures_code)
    if not snap:
        return {"error": f"無 {futures_code} 資料"}

    f_price = snap.get("close_price")
    if f_price is None:
        return {"error": "期貨無報價"}

    if spot is None:
        spot = estimate_weighted_index()
    if spot is None:
        return {"error": "無法估算現貨指數"}

    expiry = next_expiry_date()
    days_left = max((expiry - datetime.now()).days, 1)
    fair_price = theoretical_futures_price(spot, days_left)
    basis = round(f_price - spot, 2)
    fair_basis = round(fair_price - spot, 2) if fair_price else None
    deviation = round(basis - fair_basis, 2) if fair_basis is not None else None

    # 動態門檻
    stats = compute_basis_stats(futures_code)
    threshold = round(stats["std"] * 1.5, 2)

    # 避險訊號
    signal = None
    action = None
    if deviation is not None and threshold > 0:
        if deviation > threshold:
            signal = "sell"
            action = f"期貨偏貴 {deviation} 點 (>門檻 {threshold}) → 放空期貨避險"
        elif deviation < -threshold:
            signal = "buy"
            action = f"期貨偏便宜 {abs(deviation)} 點 (>門檻 {threshold}) → 買進期貨"
        else:
            signal = "hold"
            action = f"基差在正常範圍內 (偏離 {deviation} 點 ≦ 門檻 {threshold} 點)"

    # 避險口數建議
    contract_multiplier = 50 if "TXFPM" in futures_code else 200  # 小型 50, 大型 200
    hedge_value_per_lot = f_price * contract_multiplier

    return {
        "futures_code": futures_code,
        "futures_price": f_price,
        "spot_index": spot,
        "basis": basis,
        "fair_price": fair_price,
        "fair_basis": fair_basis,
        "deviation": deviation,
        "threshold": threshold,
        "basis_mean": stats["mean"],
        "basis_std": stats["std"],
        "signal": signal,
        "action": action,
        "days_to_expiry": days_left,
        "expiry_date": expiry.strftime("%Y-%m-%d"),
        "contract_multiplier": contract_multiplier,
        "hedge_value_per_lot": int(hedge_value_per_lot),
        "large_traders": fetch_large_trader_position(),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


def analyze_stock_futures(stock_codes, futures_codes):
    """個股期貨避險分析（回傳 list）。"""
    results = []
    for i, code in enumerate(stock_codes):
        stock = _read_snapshot(code)
        if not stock or not stock.get("close_price"):
            continue

        # 找對應的期貨代碼
        fut_code = futures_codes[i] if i < len(futures_codes) else None
        fut_snap = _read_snapshot(fut_code) if fut_code else None

        stock_price = stock["close_price"]
        fut_price = fut_snap["close_price"] if fut_snap else None

        basis = round(fut_price - stock_price, 2) if fut_price else None
        expiry = next_expiry_date()
        days_left = max((expiry - datetime.now()).days, 1)
        fair = theoretical_futures_price(stock_price, days_left)

        dev = None
        signal = None
        if basis is not None and fair is not None:
            fair_b = round(fair - stock_price, 2)
            dev = round(basis - fair_b, 2)
            if abs(dev) > 5:  # 個股期門檻 5 點
                signal = "sell" if dev > 0 else "buy"

        results.append({
            "stock_id": code,
            "stock_name": stock.get("stock_name", code),
            "stock_price": stock_price,
            "futures_code": fut_code,
            "futures_price": fut_price,
            "basis": basis,
            "fair_price": fair,
            "deviation": dev,
            "signal": signal,
            "days_to_expiry": days_left,
        })
    return results


# ---- API 端點 ----

@hedge_bp.route("/")
def index():
    return render_template_string(HTML)


@hedge_bp.route("/api/hedge")
def api_hedge():
    """回傳 TXF 避險分析 JSON。"""
    result = analyze_hedge("TXFPM1")
    # 個股期貨
    stocks = get_watchlist_stocks()
    futures_list = get_watchlist_futures()
    stock_results = analyze_stock_futures(stocks, futures_list)
    result["stock_futures"] = stock_results
    return jsonify(result)


@hedge_bp.route("/api/large_traders")
def api_large_traders():
    """回傳大戶動向。"""
    data = fetch_large_trader_position()
    return jsonify(data or {"error": "無法取得大戶資料"})


# ---- HTML ----

HTML = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>避險儀表板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:'Microsoft YaHei',sans-serif;padding:16px}
h1{font-size:20px;color:#58a6ff;margin-bottom:16px}
h2{font-size:16px;color:#c9d1d9;margin:12px 0 8px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:800px){.grid2{grid-template-columns:1fr}}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.row{display:flex;justify-content:space-between;margin:4px 0;font-size:13px}
.big{font-size:28px;font-weight:bold}
.up{color:#f85149}.down{color:#3fb950}.muted{color:#8b949e}
.warn{color:#d2991d}.ok{color:#3fb950}
.signal-box{padding:12px;border-radius:8px;margin:8px 0;font-size:14px;font-weight:bold}
.signal-sell{background:#da363322;border:1px solid #da3633;color:#f85149}
.signal-buy{background:#23863622;border:1px solid #238636;color:#3fb950}
.signal-hold{background:#6e768122;border:1px solid #6e7681;color:#8b949e}
table{width:100%;border-collapse:collapse;font-size:12px}
th{color:#8b949e;text-align:right;padding:4px 8px;border-bottom:1px solid #21262d}
td{text-align:right;padding:4px 8px;border-bottom:1px solid #21262d}
td.left{text-align:left}
.bar{height:6px;border-radius:3px;background:#21262d;margin:4px 0}
.bar-fill{height:100%;border-radius:3px}
.bar-fill.short{background:#f85149}.bar-fill.long{background:#3fb950}
</style>
</head>
<body>
<h1>避險儀表板</h1>

<div class="grid2">

<!-- TXF 期貨避險 -->
<div class="card">
<h2>台指期貨 TXFPM1</h2>
<div id="txfPanel">載入中...</div>
</div>

<!-- 大戶動向 -->
<div class="card">
<h2>大戶動向 (前5/前10)</h2>
<div id="traderPanel">載入中...</div>
</div>
</div>

<!-- 個股期貨 -->
<h2>個股期貨避險</h2>
<div class="card" id="stockFutures">載入中...</div>

<div style="margin-top:12px;font-size:11px;color:#484f58">
  理論期貨價 = 現貨 × (1 + 1.5% × 到期天數/365)<br>
  動態門檻 = 歷史基差標準差 × 1.5<br>
  避險口數 = 現貨市值 / (期貨價 × 合約乘數)<br>
  <a href="/" style="color:#58a6ff">← 回個股監控</a>
</div>

<script>
function fmt(n,d=2){return n!=null?Number(n).toFixed(d):'--'}
function vol(n){return n!=null?Math.round(n/1000).toLocaleString():'--'}
async function refresh(){
  try{
    const r=await fetch('/hedge/api/hedge');
    const d=await r.json();
    renderTXF(d);
    renderTraders(d.large_traders);
    renderStockFutures(d.stock_futures);
    document.getElementById('status').textContent='更新 '+new Date().toLocaleTimeString();
  }catch(e){}
}

function renderTXF(d){
  if(d.error){document.getElementById('txfPanel').innerHTML='<span class="muted">'+d.error+'</span>';return;}
  const sigCls=d.signal==='sell'?'signal-sell':d.signal==='buy'?'signal-buy':'signal-hold';
  const sigText=d.signal==='sell'?'放空避險':d.signal==='buy'?'買進期貨':'觀望';
  document.getElementById('txfPanel').innerHTML=`
<div class="row"><span>現貨指數 (估)</span><span class="big">${fmt(d.spot_index,0)}</span></div>
<div class="row"><span>期貨成交價</span><span class="big">${fmt(d.futures_price,0)}</span></div>
<div class="row"><span>基差</span><span class="${d.basis>=0?'up':'down'}">${d.basis>=0?'+'+fmt(d.basis,1):fmt(d.basis,1)} 點</span></div>
<div class="row"><span>理論期貨價</span><span>${fmt(d.fair_price,0)}</span></div>
<div class="row"><span>理論基差</span><span>${d.fair_basis!=null?'+'+fmt(d.fair_basis,1):'--'} 點</span></div>
<div class="row"><span>偏離度</span><span class="${Math.abs(d.deviation)>d.threshold?'warn':'ok'}">${d.deviation>=0?'+'+fmt(d.deviation,1):fmt(d.deviation,1)} 點</span></div>
<div class="row"><span>動態門檻 (±1.5σ)</span><span>±${fmt(d.threshold,1)} 點</span></div>
<div class="row"><span>歷史基差均值</span><span>${d.basis_mean>=0?'+'+fmt(d.basis_mean,1):fmt(d.basis_mean,1)} (±${fmt(d.basis_std,1)})</span></div>
<div class="row"><span>到期日</span><span>${d.expiry_date} (剩 ${d.days_to_expiry} 天)</span></div>
<div class="row"><span>合約乘數</span><span>${d.contract_multiplier} 點/口</span></div>
<div class="row"><span>每口避險價值</span><span>${(d.hedge_value_per_lot/1e4).toFixed(2)} 萬</span></div>
<div class="signal-box ${sigCls}">${sigText}: ${d.action||''}</div>
`;
}

function renderTraders(data){
  if(!data||!data.TXF){document.getElementById('traderPanel').innerHTML='<span class="muted">無大戶資料（非交易時段或資料延遲）</span>';return;}
  const t=data.TXF;
  const pct5=t.top5_net?(t.top5_net/((t.top5_long+t.top5_short)/2)*100).toFixed(1):'--';
  const pct10=t.top10_net?(t.top10_net/((t.top10_long+t.top10_short)/2)*100).toFixed(1):'--';
  document.getElementById('traderPanel').innerHTML=`
<table>
<tr><th></th><th>多方</th><th>空方</th><th>淨部位</th><th>淨%</th></tr>
<tr><td class="left">前5大</td><td>${t.top5_long?.toLocaleString()||'--'}</td><td class="down">${t.top5_short?.toLocaleString()||'--'}</td><td class="${t.top5_net>=0?'up':'down'}">${t.top5_net>=0?'+'+t.top5_net.toLocaleString():t.top5_net?.toLocaleString()||'--'}</td><td>${pct5}%</td></tr>
<tr><td class="left">前10大</td><td>${t.top10_long?.toLocaleString()||'--'}</td><td class="down">${t.top10_short?.toLocaleString()||'--'}</td><td class="${t.top10_net>=0?'up':'down'}">${t.top10_net>=0?'+'+t.top10_net.toLocaleString():t.top10_net?.toLocaleString()||'--'}</td><td>${pct10}%</td></tr>
</table>
<p style="margin-top:8px;font-size:11px;color:#8b949e">淨部位 >0: 大戶偏多 | <0: 大戶偏空</p>
`;
}

function renderStockFutures(data){
  if(!data||!data.length){document.getElementById('stockFutures').innerHTML='<span class="muted">無個股期貨資料（請在 watchlist.json 設定 futures 欄位）</span>';return;}
  let html='<table><tr><th>股票</th><th>現股價</th><th>期貨價</th><th>基差</th><th>理論價</th><th>偏離</th><th>訊號</th></tr>';
  for(const s of data){
    const sig=s.signal==='sell'?'<span class="up">偏貴</span>':s.signal==='buy'?'<span class="down">偏宜</span>':'<span class="muted">--</span>';
    html+=`<tr>
<td class="left">${s.stock_name||s.stock_id}</td>
<td>${fmt(s.stock_price)}</td>
<td>${fmt(s.futures_price)||'--'}</td>
<td class="${s.basis>=0?'up':'down'}">${s.basis!=null?(s.basis>=0?'+'+fmt(s.basis,1):fmt(s.basis,1)):'--'}</td>
<td>${fmt(s.fair_price)||'--'}</td>
<td>${s.deviation!=null?(s.deviation>=0?'+'+fmt(s.deviation,1):fmt(s.deviation,1)):'--'}</td><td>${sig}</td></tr>`;
  }
  html+='</table>';
  document.getElementById('stockFutures').innerHTML=html;
}

refresh();
setInterval(refresh, 2000);
</script>
<div style="font-size:10px;color:#484f58;margin-top:8px" id="status"></div>
</body>
</html>"""


def register(app):
    """註冊 Blueprint 到 Flask app。"""
    app.register_blueprint(hedge_bp)
