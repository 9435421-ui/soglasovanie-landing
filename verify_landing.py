import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 2000})
        # Since it's a static file, we can open it directly or run a local server
        import os
        path = os.path.abspath('index.html')
        await page.goto(f'file://{path}')
        await page.screenshot(path='landing_verification.png', full_page=True)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
