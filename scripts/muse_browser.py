"""Open Muse through the tool's selected connection and retain its browser."""
import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from muse_access import inspect_muse_access

_sessions = {}


async def open_muse_browser(proxy, cookies=None, verify_access=False):
    runtime = await async_playwright().start()
    browser = None
    try:
        browser = await runtime.chromium.launch(
            channel="chrome", headless=False, proxy=proxy,
        )
        context = await browser.new_context()
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
