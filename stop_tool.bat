@echo off
chcp 65001 > nul
title MUSE.AI AUTO BOT STOPPER
color 0c

echo ===============================================================================
echo                ĐANG DỪNG TOÀN BỘ HỆ THỐNG BOT MUSE.AI
echo ===============================================================================
echo.

echo Đang dừng Bot Server & Psiphon...
taskkill /F /IM psiphon-tunnel-core.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq Muse Bot Server*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Muse Frontend*" 2>nul
taskkill /F /FI "WINDOWTITLE eq SpinupMail Backend*" 2>nul
taskkill /F /FI "WINDOWTITLE eq Cloudflare Tunnel*" 2>nul

echo.
echo ===============================================================================
echo ĐÃ DỪNG THÀNH CÔNG TẤT CẢ DỊCH VỤ!
echo ===============================================================================
pause
