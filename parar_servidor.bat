@echo off
title America Web - Parar Servidor
echo =======================================================
echo   AMERICA WEB - ENCERRANDO SERVICOS EM SEGUNDO PLANO
echo =======================================================
echo.

powershell -Command "Stop-Process -Name python, pythonw, ngrok, cloudflared -Force -ErrorAction SilentlyContinue"

echo [OK] Servidor e Tunel foram encerrados com sucesso!
echo.
pause
