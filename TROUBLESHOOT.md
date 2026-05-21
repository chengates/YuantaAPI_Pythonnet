# Troubleshooting & Quick Reference

## 1. Process Management

### Problem: `taskkill /f /im python.exe` doesn't kill anything

Windows Store Python uses `python3.13.exe`. Universal kill command:

```powershell
# PowerShell — kills ALL Python variants
Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Stop-Process -Force
```

```cmd
:: CMD — covers all common names
taskkill /f /im python.exe /im python3.exe /im python3.13.exe 2>nul
```

### Problem: Multiple stale processes on port 5000

```
netstat -ano | findstr ":5000"
:: Kill PIDs:
taskkill /f /pid <PID>
```

**Root cause**: Each `Start-Process python ...` spawns a NEW process. If the old one wasn't killed first, both listen on port 5000. The first-bound process serves stale code.

**Fix**: Always kill before starting. Use `run.py` (single process for both services).

### Problem: Console windows multiply on each restart

**Root cause**: `Start-Process` creates a visible window even with `-WindowStyle Minimized` (it flashes briefly), and old windows aren't cleaned up.

**Fix**: Use `python run.py` directly (1 process = 1 window), or use `pythonw.exe run.py` (0 windows).

---

## 2. CSV Encoding

### Problem: `read_latest_csv` returns None for all stocks, dashboard shows "等待資料"

**Check**: `python -c "import csv; list(csv.DictReader(open('2330.csv', encoding='utf-8', errors='replace')))"`

If you get `UnicodeDecodeError`, the CSV has mixed encoding (old cp950 data + new UTF-8 data).

**Root cause**: Original `_save_to_csv_async` wrote in system default encoding (cp950 on Windows). Later code appends in UTF-8. Reading as pure UTF-8 fails on old rows.

**Fix**: Delete old CSVs and let simulator recreate them from scratch:
```powershell
Remove-Item *.csv -Exclude '@*.csv'
```

**Prevention**: Always open CSVs with `encoding="utf-8", errors="replace"`.

---

## 3. Web Dashboard

### Problem: Full page flicker on every 2-second refresh

**Root cause**: `g.innerHTML = ''` + rebuilding all cards replaces entire DOM tree. Each rebuild triggers browser layout/paint.

**Fix**: Per-card DOM with targeted `textContent` updates:
- Build card structure ONCE, store references to each `<span>` by class
- On update, only set `.textContent` on spans whose value changed
- `setText(el, val)`: skip if `el.textContent === val`

### Problem: Watchlist switching shows no data

**Check**: `curl http://localhost:5000/api/watchlists` — confirms active watchlist.
`curl http://localhost:5000/api/stocks` — confirms stocks returned.

**Root cause 1**: No CSV files exist for the new watchlist's stocks.  
**Fix**: Simulator reads `watchlist.json` automatically — add stock to JSON, data appears within 5s.

**Root cause 2**: `--stocks` CLI argument had a hardcoded default overriding the watchlist reader.  
**Fix**: Set `default=None` and read from `watchlist.json` when not specified.

### Problem: Browser shows stale data after server restart

**Fix**: Hard refresh — `Ctrl+Shift+R`.

---

## 4. Code Quality

### Problem: `IndentationError` after Edit tool

**Root cause**: The Edit tool's `old_string`/`new_string` matching can leave misaligned indentation when inserting into indented blocks.

**Check**: `python -c "import ast; ast.parse(open('file.py').read())"`

### Problem: Chinese characters garbled in terminal output

Not a real bug — Windows console uses cp950, can't render UTF-8. Use `repr()` to verify actual string values, or use a UTF-8 capable terminal (Windows Terminal, VS Code terminal).

### Problem: `.py` files written with wrong encoding

The IDE/editor should save as UTF-8. Verify: `python -c "open('file.py','rb').read()[:3]"` — BOM `\xef\xbb\xbf` is OK, but no BOM with UTF-8 content is also OK.

---

## 5. Quick Start (Clean)

```powershell
# Kill everything
.\stop.ps1

# Start fresh (single process, 1 window)
python run.py

# Open browser
start http://localhost:5000
```

## 6. File Reference

| File | Purpose |
|---|---|
| `run.py` | Single-process launcher (simulator thread + dashboard) |
| `test_simulate.py` | Generates mock OHLCV data into CSV files |
| `web_dashboard.py` | Flask + SSE real-time monitor |
| `option_pricing.py` | Black-Scholes + Put/Call Parity calculator |
| `watchlist.json` | User-editable stock watchlists |
| `start.ps1` | Kill all Python + restart dashboard |
| `stop.ps1` | Kill all Python processes |
| `YuantaAPI_Pythonnet.py` | Main API bridge (pythonnet → YuantaOneAPI.dll) |
| `cStocks.py` | K-line chart visualization |
