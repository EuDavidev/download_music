@echo off
title America Web - Status do Servidor
cls
echo =======================================================
echo   AMERICA WEB - STATUS DO SERVIDOR E LINK ONLINE
echo =======================================================
echo.

:: Verifica processos
powershell -Command "if (Get-Process pythonw, python -ErrorAction SilentlyContinue) { Write-Host ' [OK] Servidor Web (FastAPI): ATIVO' -ForegroundColor Green } else { Write-Host ' [X] Servidor Web (FastAPI): DESLIGADO' -ForegroundColor Red }"
powershell -Command "if (Get-Process cloudflared -ErrorAction SilentlyContinue) { Write-Host ' [OK] Tunel Cloudflare: ATIVO' -ForegroundColor Green } else { Write-Host ' [X] Tunel Cloudflare: DESLIGADO' -ForegroundColor Red }"

echo.
echo -------------------------------------------------------
echo   LINKS DE ACESSO:
echo -------------------------------------------------------
echo   • Local: http://localhost:8000
echo.

:: Busca o link trycloudflare no log
if exist "d:\download_music\tunnel.log" (
    powershell -Command "$link = Select-String -Path 'd:\download_music\tunnel.log' -Pattern 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | Select-Object -Last 1; if ($link) { Write-Host '   • Link Publico Cloudflare: ' -NoNewline; Write-Host $link.Matches.Value -ForegroundColor Cyan } else { Write-Host '   • Link Cloudflare ainda conectando...' }"
) else (
    echo   • Arquivo de log do tunnel ainda nao gerado.
)

echo.
echo =======================================================
echo.
pause
