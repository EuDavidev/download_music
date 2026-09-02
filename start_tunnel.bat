@echo off
title America Web - Ngrok Tunnel
echo =======================================================
echo   AMERICA WEB - NGROK TUNNEL (URL FIXA)
echo =======================================================
echo.
echo Conectando ao Ngrok... Link: https://unpaved-counting-patio.ngrok-free.dev
echo.
ngrok http --url https://unpaved-counting-patio.ngrok-free.dev 8000
pause

