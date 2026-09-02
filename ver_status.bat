@echo off
title America Web - Status do Servidor
cls
echo =======================================================
echo   AMERICA WEB - STATUS DO SERVIDOR E LINK ONLINE
echo =======================================================
echo.

:: Verifica processos
powershell -Command "if (Get-Process pythonw, python -ErrorAction SilentlyContinue) { Write-Host ' [OK] Servidor Web (FastAPI): ATIVO' -ForegroundColor Green } else { Write-Host ' [X] Servidor Web (FastAPI): DESLIGADO' -ForegroundColor Red }"
powershell -Command "if (Get-Process ngrok, cloudflared -ErrorAction SilentlyContinue) { Write-Host ' [OK] Tunel Online (Ngrok): ATIVO' -ForegroundColor Green } else { Write-Host ' [X] Tunel Online (Ngrok): DESLIGADO' -ForegroundColor Red }"

echo.
echo -------------------------------------------------------
echo   LINKS DE ACESSO FIXOS:
echo -------------------------------------------------------
echo   • Local (Computador): http://localhost:8000
echo.
powershell -Command "Write-Host '   • Celular / Internet (URL Fixa): ' -NoNewline; Write-Host 'https://unpaved-counting-patio.ngrok-free.dev' -ForegroundColor Cyan"

echo.
echo =======================================================
echo.
pause

