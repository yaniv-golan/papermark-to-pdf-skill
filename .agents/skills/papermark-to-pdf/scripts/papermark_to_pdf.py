#!/usr/bin/env python3
"""
Convert a Papermark shared deck URL to a PDF file.

Usage:
    python papermark_to_pdf.py <papermark-url> [output.pdf] [--debug]

If output.pdf is omitted, the filename is derived from the deck's page title.

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

--debug prints every CloudFront URL intercepted (not just page images),
useful when diagnosing 0-image captures or unexpected URL patterns.
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


def title_to_filename(title: str) -> str:
    """Derive a safe PDF filename from the page title."""
    # Strip common Papermark suffixes
    for suffix in (" | Papermark", " - Papermark", "| Papermark", "- Papermark"):
        if suffix in title:
            title = title[: title.index(suffix)].strip()
    # Keep alphanumerics, spaces, hyphens; collapse the rest to underscores
    safe = re.sub(r"[^\w\s-]", "", title).strip()
    safe = re.sub(r"[\s-]+", "_", safe)
    return (safe[:60] or "deck") + ".pdf"


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


async def convert_papermark_to_pdf(
    url: str, output_path: str | None, debug: bool = False
) -> None:
    """Download all slides from a Papermark URL and save as PDF."""

    with tempfile.TemporaryDirectory() as tmpdir:
        saved_images: dict[int, str] = {}
        total_slides = [0]  # mutable list so handle_response closure can read updates

        async with async_playwright() as p:
            # Allow container environments to provide a system Chromium by setting
            # PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH. Playwright does not read this
            # variable automatically — we pass it explicitly to launch().
            executable_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None
            if executable_path:
                print(f"Using system Chromium: {executable_path}")
            browser = await p.chromium.launch(headless=True, executable_path=executable_path)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            # Intercept CloudFront image responses and save them to disk
            async def handle_response(response):
                resp_url = response.url
                if "cloudfront.net" not in resp_url:
                    return
                if debug:
                    print(f"  [debug] CloudFront: {resp_url}")
                if "/page-" not in resp_url:
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
                        total_str = (
                            f"/{total_slides[0]}" if total_slides[0] else ""
                        )
                        print(
                            f"  Captured page {num}{total_str}"
                            f" ({len(body):,} bytes)"
                        )
                except Exception as e:
                    print(f"  Warning: failed to capture a response: {e}")

            page.on("response", handle_response)

            # Navigate to the deck
            print(f"Opening {url} ...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # Derive output path from page title if not provided
            if output_path is None:
                title = await page.title()
                filename = title_to_filename(title) if title else "deck.pdf"
                output_path = filename
                print(f"Output: {output_path!r}  (from page title: {title!r})")

            # Count total slide images in the DOM
            total_imgs = await page.eval_on_selector_all(
                'img[alt^="Page"]', "imgs => imgs.length"
            )
            total_slides[0] = total_imgs  # make available to handle_response

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
                if current_captured > prev_captured:
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

        # Verification
        if total_imgs and len(pages) != total_imgs:
            print(
                f"  Warning: captured {len(pages)} pages but deck reported"
                f" {total_imgs} slides — some pages may be missing"
            )
        elif total_imgs:
            print(f"  Verified: {len(pages)} pages match deck slide count")

        if size < 1024:
            print(
                f"  Warning: PDF is unusually small ({size} bytes)"
                " — may be empty or corrupt"
            )


def main():
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    debug = "--debug" in flags

    if len(positional) < 1 or len(positional) > 2:
        print(f"Usage: {sys.argv[0]} <papermark-url> [output.pdf] [--debug]")
        sys.exit(1)

    url = positional[0]
    output_path = positional[1] if len(positional) == 2 else None

    if not is_papermark_url(url):
        print(f"Warning: URL doesn't look like a Papermark view link: {url}")

    asyncio.run(convert_papermark_to_pdf(url, output_path, debug=debug))


if __name__ == "__main__":
    main()
