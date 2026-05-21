# Start dashboard + simulator cleanly
cmd /c "taskkill /f /im python.exe 2>nul"
Start-Sleep 2
Start-Process python -ArgumentList "test_simulate.py", "--interval", "5" -WindowStyle Minimized
Start-Process python -ArgumentList "web_dashboard.py", "--port", "5000" -WindowStyle Minimized
Write-Host "Dashboard: http://localhost:5000"
