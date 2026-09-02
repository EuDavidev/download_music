@echo off
title America Web - Servidor 24h
cd /d "%~dp0"

:: 1. Inicia o servidor Python FastAPI em segundo plano
start "America Web Server" /min python run_web.py

:: 2. Aguarda 3 segundos para o servidor subir
timeout /t 3 /nobreak >nul

:: 3. Inicia o Tunel Ngrok com Link Fixo
echo Iniciando Ngrok com URL Fixa: https://unpaved-counting-patio.ngrok-free.dev
ngrok http --url https://unpaved-counting-patio.ngrok-free.dev 8000 --log "d:\download_music\ngrok.log"



