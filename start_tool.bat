@echo off
chcp 65001 > nul
title MUSE.AI AUTO BOT LAUNCHER
color 0b

echo ===============================================================================
echo            KHỞI ĐỘNG HỆ THỐNG BOT TỰ ĐỘNG REG ACC MUSE.AI (META)
echo ===============================================================================
echo.

cd /d "%~dp0"

:: 1. Check & start Bot Server (Port 8790) with G0 Runtime Handshake
powershell -NoProfile -Command ^
    "$conn = Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue; " ^
    "if ($conn) { " ^
    "    try { " ^
    "        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8790/api/bot/runtime' -TimeoutSec 2; " ^
    "        $status = Invoke-RestMethod -Uri 'http://127.0.0.1:8790/api/bot/status' -TimeoutSec 2; " ^
    "        $exp_fp = (python scripts/bot_server.py --fingerprint).Trim(); " ^
    "        $exp_sha = (git rev-parse HEAD).Trim(); " ^
    "        if ($resp.ok -and ($resp.build_sha -eq $exp_sha) -and ($resp.network_revision -eq 'MUSE-GEO-001-G0-G5') -and ($resp.source_fingerprint -eq $exp_fp) -and ($null -ne $status.isRunning)) { " ^
    "            Write-Host ('[OK] Bot Server Daemon dang chay dung runtime (PID: ' + $resp.pid + ', Rev: ' + $resp.network_revision + ', SHA: ' + $resp.build_sha.Substring(0,[Math]::Min(7, $resp.build_sha.Length)) + ', FP: ' + $resp.source_fingerprint + ')') -ForegroundColor Green; " ^
    "            exit 1 " ^
    "        } else { " ^
    "            Write-Host '[CANH BAO] Cong 8790 phan hoi nhung sai revision/source fingerprint hoac thieu runtime (STALE_PROCESS).' -ForegroundColor Yellow; " ^
    "            exit 2 " ^
    "        } " ^
    "    } catch { " ^
    "        Write-Host '[CANH BAO] Cong 8790 dang bi chiem boi tien trinh khong ro (PORT_OCCUPIED_NOT_OWNED).' -ForegroundColor Red; " ^
    "        exit 2 " ^
    "    } " ^
    "} else { exit 0 }"
set "BOT_CHECK_CODE=%errorlevel%"
if "%BOT_CHECK_CODE%"=="1" (
    echo [1/3] Bot Server Daemon [Port 8790] đã được xác thực runtime identity, tiếp tục sử dụng.
) else if "%BOT_CHECK_CODE%"=="2" (
    echo [1/3] CẢNH BÁO: Cổng 8790 đang bị chiếm hoặc tiến trình không phản hồi runtime handshake. Bỏ qua khởi động để bảo vệ tiến trình khác.
) else (
    echo [1/3] Đang khởi động Bot Server Daemon [Port 8790]...
    start "Muse Bot Server [Port 8790]" cmd /k "color 0a & python -u scripts/bot_server.py"
)

:: 2. Check & start Frontend UI (Port 5173)
powershell -Command "if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [2/3] Frontend Web UI [Port 5173] đã đang chạy, bỏ qua khởi động trùng lặp.
) else (
    echo [2/3] Đang khởi động Frontend Web UI [Port 5173]...
    start "Muse Frontend UI [Port 5173]" cmd /k "color 0b & pnpm -C packages/frontend dev --host 127.0.0.1"
)

:: 3. Check & start Backend Worker (Port 8787)
powershell -Command "if (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [3/3] SpinupMail Backend [Port 8787] đã đang chạy, bỏ qua khởi động trùng lặp.
) else (
    echo [3/3] Đang khởi động Backend API Worker [Port 8787]...
    start "SpinupMail Backend [Port 8787]" cmd /k "color 0e & pnpm -C packages/backend dev"
)

echo.
echo ===============================================================================
echo ĐANG KIỂM TRA MỨC ĐỘ SẴN SÀNG CỦA CÁC DỊCH VỤ (READINESS PROBE)...

powershell -Command "$ready = $false; for ($i=0; $i -lt 15; $i++) { try { $r1 = Invoke-WebRequest -Uri 'http://127.0.0.1:8790/api/bot/status' -UseBasicParsing -TimeoutSec 1; $r2 = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1; $r3 = Invoke-WebRequest -Uri 'http://127.0.0.1:8787/api/public/domains' -UseBasicParsing -TimeoutSec 1; if ($r1.StatusCode -eq 200 -and $r2.StatusCode -eq 200 -and $r3.StatusCode -eq 200) { $ready = $true; break } } catch {}; Start-Sleep -Seconds 1 }; if ($ready) { Write-Host 'TẤT CẢ DỊCH VỤ ĐÃ PHẢN HỒI SẴN SÀNG!' -ForegroundColor Green } else { Write-Host 'Lưu ý: Một số dịch vụ phản hồi chậm hoặc đang khởi tạo.' -ForegroundColor Yellow }"

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
