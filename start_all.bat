@echo off
title America Web - Servidor 24h
cd /d "%~dp0"

:: 1. Inicia o servidor Python FastAPI em segundo plano
start "America Web Server" /min python run_web.py

:: 2. Aguarda 3 segundos para o servidor subir
timeout /t 3 /nobreak >nul

:: 3. Inicia o Tunel Cloudflare salvando log com link
cloudflared tunnel --url http://localhost:8000 --logfile tunnel.log


