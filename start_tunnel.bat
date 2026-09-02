@echo off
title America Web - Cloudflare Tunnel
echo =======================================================
echo   AMERICA WEB - CLOUDFLARE TUNNEL (ACESSO PUBLICO)
echo =======================================================
echo.
echo Conectando ao Cloudflare... Aguarde a geracao do link HTTPS.
echo.
cloudflared tunnel --url http://localhost:8000
pause
