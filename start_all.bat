@echo off
title America Web - Servidor 24h
echo =======================================================
echo   AMERICA WEB - INICIANDO SERVIDOR E TUNEL (24H)
echo =======================================================
echo.

cd /d "%~dp0"

:: 1. Inicia o servidor Python FastAPI em segundo plano / nova janela minimizada
start "America Web Server" /min python run_web.py

:: 2. Aguarda 3 segundos para o servidor subir
timeout /t 3 /nobreak >nul

:: 3. Inicia o Tunel Cloudflare
echo Iniciando Cloudflare Tunnel...
cloudflared tunnel --url http://localhost:8000
