"""Take screenshots of each app page for the landing page.

Usage:
    python scripts/take_screenshots.py

Requires:
    pip install playwright
    python -m playwright install chromium
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "screenshots"

PAGES = [
    ("dashboard", "/dashboard", 3000),
    ("sir-henry", "/sir-henry", 3000),
    ("retirement", "/retirement", 4000),
    ("portfolio", "/portfolio", 3000),
    ("tax-strategy", "/tax-strategy", 3000),
    ("budget", "/budget", 3000),
    ("goals", "/goals", 3000),
    ("household", "/household", 3000),
    ("recurring", "/recurring", 3000),
    ("accounts", "/accounts", 3000),
]


async def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,  # Retina quality
        )
        page = await context.new_page()

        for name, path, wait_ms in PAGES:
            url = f"http://localhost:3000{path}"
            print(f"  Navigating to {url} ...")
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(wait_ms)

            # Scroll to top
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)

            out = SCREENSHOTS_DIR / f"{name}.png"
            await page.screenshot(path=str(out), full_page=False)
            print(f"  [OK] Saved {out.name}")

        await browser.close()

    print(f"\nDone! {len(PAGES)} screenshots saved to {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
