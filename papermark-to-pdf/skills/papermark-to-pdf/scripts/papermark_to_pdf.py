#!/usr/bin/env python3
"""
Convert a Papermark shared deck URL to a PDF file.

Usage:
    python papermark_to_pdf.py <papermark-url> <output.pdf>

How it works:
    1. Opens the Papermark viewer in a headless Chromium browser
    2. Intercepts CloudFront image responses as they load
    3. Navigates through all slides (ArrowRight key, with button-click fallback)
       to trigger lazy loading of each page
    4. Saves intercepted images to a temp directory
    5. Compiles all images into a single PDF using Pillow

The key insight is that Papermark lazy-loads slides behind per-page signed
CloudFront URLs. You can't curl them (session-tied), can't fetch() them
(CORS), and can't canvas-extract them (tainted). But Playwright's response
interception captures the actual binary data as the browser loads each image.

Navigation uses ArrowRight keyboard input (more reliable than positional
button detection, which breaks on viewport changes). Button-click is kept
as a fallback.
"""

import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

PAPERMARK_DOMAINS = ("papermark.com", "papermark.io")


def is_papermark_url(url: str) -> bool:
    return any(domain in url for domain in PAPERMARK_DOMAINS)


async def try_navigate_next(page) -> bool:
    """
    Advance to the next slide. Tries ArrowRight key first (reliable across
    all viewport sizes), then falls back to clicking the positional next button.
    Returns True if we likely moved forward, False if nothing was clickable.
    """
    # Primary: keyboard navigation — works regardless of button position
    await page.keyboard.press("ArrowRight")
    await asyncio.sleep(0.05)  # Let the event propagate

    # Check if the page responded (heuristic: did the URL or slide counter change?)
    # We don't need to confirm — just return True optimistically; the image
    # interception loop will detect if we're stuck.
    return True


async def try_click_next_button(page) -> bool:
    """
    Fallback: click a button in the right half of the screen that looks like
    a next/forward button. Returns True if a candidate was found and clicked.
    """
    try:
        viewport = page.viewport_size or {"width": 1920, "height": 1080}
        mid_x = viewport["width"] / 2
        mid_y = viewport["height"] / 2
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            box = await btn.bounding_box()
            if (
                box
                and box["x"] > mid_x  # right half of screen
                and abs(box["y"] - mid_y) < mid_y * 0.5  # vertically centered-ish
                and box["width"] > 20
            ):
                await btn.click()
                await asyncio.sleep(0.8)
                return True
    except Exception:
        pass
    return False


async def convert_papermark_to_pdf(url: str, output_path: str) -> None:
    """Download all slides from a Papermark URL and save as PDF."""

    with tempfile.TemporaryDirectory() as tmpdir:
        saved_images: dict[int, str] = {}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            # Intercept CloudFront image responses and save them to disk
            async def handle_response(response):
                resp_url = response.url
                if "cloudfront.net" not in resp_url or "/page-" not in resp_url:
                    return
                try:
                    body = await response.body()
                    match = re.search(r"/page-(\d+)\.(jpeg|png)", resp_url)
                    if match:
                        num = int(match.group(1))
                        ext = match.group(2)
                        filepath = os.path.join(tmpdir, f"page-{num}.{ext}")
                        with open(filepath, "wb") as f:
                            f.write(body)
                        saved_images[num] = filepath
                        print(f"  Captured page {num} ({len(body):,} bytes)")
                except Exception as e:
                    print(f"  Warning: failed to capture a response: {e}")

            page.on("response", handle_response)

            # Navigate to the deck
            print(f"Opening {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # Count total slide images in the DOM
            total_imgs = await page.eval_on_selector_all(
                'img[alt^="Page"]', "imgs => imgs.length"
            )
            if total_imgs == 0:
                print(
                    "Warning: found 0 slide images in DOM. "
                    "The page structure may have changed or the URL may require authentication."
                )
            print(f"Deck has {total_imgs} slides")
            print(f"Initial load captured {len(saved_images)} images")

            # Click into the viewer first so it receives keyboard events
            try:
                await page.click("body")
                await asyncio.sleep(0.3)
            except Exception:
                pass

            # Navigate through remaining slides
            # Primary: ArrowRight key. Fallback: positional button click.
            max_attempts = (total_imgs or 100) + 10  # safety margin
            stall_count = 0
            prev_captured = len(saved_images)

            for i in range(max_attempts):
                if total_imgs and len(saved_images) >= total_imgs:
                    break

                await try_navigate_next(page)
                await asyncio.sleep(0.8)

                current_captured = len(saved_images)
                pct = (
                    f" ({current_captured}/{total_imgs})"
                    if total_imgs
                    else f" ({current_captured} captured)"
                )
                if current_captured > prev_captured:
                    print(f"  Progress{pct}")
                    stall_count = 0
                else:
                    stall_count += 1

                # If keyboard navigation isn't making progress, try the button
                if stall_count == 3:
                    clicked = await try_click_next_button(page)
                    if not clicked:
                        # No button found — probably on the last slide
                        break
                    stall_count = 0

                # Hard stop if completely stuck for too long
                if stall_count >= 8:
                    print("  No new pages after several attempts — stopping navigation.")
                    break

                prev_captured = current_captured

            # Small grace period for any in-flight responses to arrive
            await asyncio.sleep(2)
            await browser.close()

        # --- Compile images into PDF ---
        if not saved_images:
            print("Error: No images were captured. The URL may be invalid or gated.")
            sys.exit(1)

        print(f"\nCaptured {len(saved_images)} of {total_imgs} slides")

        # Sort by page number and open with Pillow
        pages = []
        for num in sorted(saved_images.keys()):
            img = Image.open(saved_images[num])
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            pages.append(img)

        # Save as multi-page PDF
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        pages[0].save(
            output_path,
            save_all=True,
            append_images=pages[1:],
            resolution=150.0,
        )

        size = os.path.getsize(output_path)
        print(f"\nPDF saved: {output_path}")
        print(f"  Pages: {len(pages)}")
        print(f"  Size:  {size / 1024 / 1024:.1f} MB")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <papermark-url> <output.pdf>")
        sys.exit(1)

    url = sys.argv[1]
    output_path = sys.argv[2]

    if not is_papermark_url(url):
        print(f"Warning: URL doesn't look like a Papermark view link: {url}")

    asyncio.run(convert_papermark_to_pdf(url, output_path))


if __name__ == "__main__":
    main()
