from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 950})
    page.goto("http://127.0.0.1:5173/muse", wait_until="networkidle")
    
    # 1. Click 'Kiểm Tra IP Ngay' for VPN Máy
    page.get_by_role("button", name="Kiểm Tra IP Ngay").click()
    time.sleep(3)
    page.screenshot(path="scripts/muse_check_vpn_tested.png", full_page=True)
    
    # 2. Select Proxy Riêng and enter custom proxy
    page.get_by_role("button", name="Proxy Riêng").click()
    page.locator('input[placeholder*="123.45.67.89"]').fill("socks5://193.25.215.182:22222")
    page.get_by_role("button", name="Kiểm Tra IP Ngay").click()
    time.sleep(3)
    page.screenshot(path="scripts/muse_check_proxy_tested.png", full_page=True)
    
    browser.close()
print("Tests finished successfully")
