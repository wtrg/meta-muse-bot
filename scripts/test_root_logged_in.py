from playwright.sync_api import sync_playwright
import json, time

with open('scripts/muse_accounts.json', 'r', encoding='utf-8') as f:
    accs = json.load(f)

cookies = accs[0]['cookies']

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(locale='en-US', timezone_id='America/New_York')
    ctx.add_cookies(cookies)
    page = ctx.new_page()
    page.goto('https://muse.ai/', wait_until='domcontentloaded')
    time.sleep(3)
    print('Final URL when opening muse.ai with cookies:', page.url)
    print('Title:', page.title())
    print('Body text:', page.inner_text('body')[:400])
    browser.close()
