@echo off
chcp 65001 > nul
title MUSE.AI AUTO BOT LAUNCHER
color 0b

echo ===============================================================================
echo            KHỞI ĐỘNG HỆ THỐNG BOT TỰ ĐỘNG REG ACC MUSE.AI (META)
echo ===============================================================================
echo.

cd /d "%~dp0"

echo [1/4] Đang khởi động Bot Server Daemon (Port 8789)...
start "Muse Bot Server [Port 8789]" cmd /k "color 0a & python -u scripts/bot_server.py"

echo [2/4] Đang khởi động Frontend Web UI (Port 5173)...
start "Muse Frontend UI [Port 5173]" cmd /k "color 0b & pnpm -C packages/frontend dev --host 127.0.0.1"

echo [3/4] Đang khởi động Backend API Worker (Port 8787)...
start "SpinupMail Backend [Port 8787]" cmd /k "color 0e & pnpm -C packages/backend dev"

echo [4/4] Đang khởi động Cloudflare Tunnel (Cổng OTP Trực Tuyến Công Khai)...
start "Cloudflare Tunnel [Public OTP]" cmd /k "color 0d & npx --yes cloudflared tunnel --url http://127.0.0.1:5173"

echo.
echo ===============================================================================
echo ĐANG ĐỢI CÁC DỊCH VỤ KHỞI CHẠY (khoảng 3 giây)...
timeout /t 3 /nobreak > nul

echo.
echo ===============================================================================
echo ĐÃ KHỞI ĐỘNG THÀNH CÔNG TẤT CẢ CÁC DỊCH VỤ!
echo.
echo  • Giao Diện Tool Muse:  http://127.0.0.1:5173/muse
echo  • Trang OTP Nội Bộ:     http://127.0.0.1:5173/otp
echo  • Bot Server Daemon:    http://127.0.0.1:8789
echo  • Backend D1 Database:  http://127.0.0.1:8787
echo ===============================================================================
echo.
echo Đang tự động mở trình duyệt truy cập Tool...
start http://127.0.0.1:5173/muse

echo.
echo (Cửa sổ này có thể đóng lại. Các dịch vụ đang chạy trong các cửa sổ riêng.)
pause
