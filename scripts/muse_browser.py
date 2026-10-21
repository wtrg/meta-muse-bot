"""Open Muse through the tool's selected connection and retain its browser."""
import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from muse_access import inspect_muse_access

import os

_sessions = {}


def get_preferred_browser_channel():
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    if any(os.path.exists(p) for p in edge_paths):
        return "msedge"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
    ]
    if any(os.path.exists(p) for p in chrome_paths):
        return "chrome"
    return None


async def open_muse_browser(proxy, cookies=None, verify_access=False):
    runtime = await async_playwright().start()
    browser = None
    try:
        channel_to_use = get_preferred_browser_channel()
        launch_kwargs = {
            "headless": False,
            "proxy": proxy,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-default-browser-check",
                "--no-first-run"
            ]
        }
        if channel_to_use:
            launch_kwargs["channel"] = channel_to_use
        browser = await runtime.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/New_York"
        )
        if hasattr(context, "add_init_script") and callable(getattr(context, "add_init_script")):
            try:
                res = context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        navigation_pending = False
        try:
            await page.goto("https://muse.ai/", wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            if not verify_access:
                raise
            navigation_pending = True
        key = id(browser)
        _sessions[key] = (runtime, browser)

        async def cleanup():
            session = _sessions.pop(key, None)
            if session:
                await session[0].stop()

        browser.on("disconnected", lambda *_: asyncio.create_task(cleanup()))
        if not browser.is_connected():
            await cleanup()
            raise RuntimeError("Trình duyệt đã đóng trước khi mở xong Muse.")
        if verify_access:
            if navigation_pending:
                result = {"status": "ACCESS_UNVERIFIED", "message": "Muse tải chậm; chưa xác minh được truy cập. Cửa sổ được giữ mở để bạn kiểm tra."}
            else:
                try:
                    result = await inspect_muse_access(page, continue_saved_login=True)
                except PlaywrightError:
                    result = {"status": "ACCESS_UNVERIFIED", "message": "Chưa kiểm tra xong đăng nhập. Hãy tiếp tục trong cửa sổ Muse đang mở; chưa có bằng chứng chặn vùng."}
            result.update(url=page.url, cookies=await context.cookies())
            return result
        return page.url
    except Exception:
        if browser:
            _sessions.pop(id(browser), None)
        if browser and browser.is_connected():
            await browser.close()
        await runtime.stop()
        raise
