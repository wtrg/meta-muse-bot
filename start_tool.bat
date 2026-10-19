@echo off
chcp 65001 > nul
title MUSE.AI AUTO BOT LAUNCHER
color 0b

echo ===============================================================================
echo            KHỞI ĐỘNG HỆ THỐNG BOT TỰ ĐỘNG REG ACC MUSE.AI (META)
echo ===============================================================================
echo.

cd /d "%~dp0"

:: 1. Check & start Bot Server (Port 8790)
powershell -Command "if (Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [1/3] Bot Server Daemon (Port 8790) đã đang chạy, bỏ qua khởi động trùng lặp.
) else (
    echo [1/3] Đang khởi động Bot Server Daemon (Port 8790)...
    start "Muse Bot Server [Port 8790]" cmd /k "color 0a & python -u scripts/bot_server.py"
)

:: 2. Check & start Frontend UI (Port 5173)
powershell -Command "if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [2/3] Frontend Web UI (Port 5173) đã đang chạy, bỏ qua khởi động trùng lặp.
) else (
    echo [2/3] Đang khởi động Frontend Web UI (Port 5173)...
    start "Muse Frontend UI [Port 5173]" cmd /k "color 0b & pnpm -C packages/frontend dev --host 127.0.0.1"
)

:: 3. Check & start Backend Worker (Port 8787)
powershell -Command "if (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [3/3] SpinupMail Backend (Port 8787) đã đang chạy, bỏ qua khởi động trùng lặp.
) else (
    echo [3/3] Đang khởi động Backend API Worker (Port 8787)...
    start "SpinupMail Backend [Port 8787]" cmd /k "color 0e & pnpm -C packages/backend dev"
)

echo.
echo ===============================================================================
echo ĐANG KIỂM TRA MỨC ĐỘ SẴN SÀNG CỦA CÁC DỊCH VỤ (READINESS PROBE)...

powershell -Command "$ready = $false; for ($i=0; $i -lt 15; $i++) { try { $r1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8790/api/bot/status' -UseBasicParsing -TimeoutSec 1; $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1; if ($r1.StatusCode -eq 200 -and $r2.StatusCode -eq 200) { $ready = $true; break } } catch {}; Start-Sleep -Seconds 1 }; if ($ready) { Write-Host 'TẤT CẢ DỊCH VỤ ĐÃ PHẢN HỒI SẴN SÀNG!' -ForegroundColor Green } else { Write-Host 'Lưu ý: Một số dịch vụ phản hồi chậm hoặc đang khởi tạo.' -ForegroundColor Yellow }"

echo.
echo ===============================================================================
echo TRẠNG THÁI HỆ THỐNG:
echo.
echo  • Giao Diện Tool Muse:  http://127.0.0.1:5173/muse
echo  • Trang OTP Nội Bộ:     http://127.0.0.1:5173/otp
echo  • Bot Server Daemon:    http://127.0.0.1:8790
echo  • Backend D1 Database:  http://127.0.0.1:8787
echo ===============================================================================
echo.
echo Đang mở trình duyệt giao diện Tool...
start http://127.0.0.1:5173/muse

echo.
echo (Cửa sổ này có thể đóng lại. Các dịch vụ đang chạy trong các cửa sổ riêng.)
pause
