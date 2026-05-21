# Stop all dashboard/simulator processes — use taskkill for reliability
cmd /c "taskkill /f /im python.exe 2>nul"
Write-Host "All Python processes stopped"
