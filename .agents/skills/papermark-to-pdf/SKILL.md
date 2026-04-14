---
name: papermark-to-pdf
description: >-
  Converts Papermark shared deck links into downloadable PDF files. Use when the user shares a papermark.com or papermark.io URL and wants it as a PDF, asks to "download this deck", "save this Papermark link as PDF", "convert this deck to PDF", "get me a PDF of this presentation", or pastes a Papermark view link and says "PDF", "save", "download", or "export". Works with any public Papermark view link (papermark.com/view/ or papermark.io/view/) regardless of page count. Handles lazy-loaded slides by intercepting CloudFront image responses via a headless browser — no manual steps required.
user-invocable: true
argument-hint: <papermark-url> [output.pdf]
metadata:
  author: yaniv-golan
  version: 1.2.0
---

# Papermark to PDF

Convert any Papermark shared deck URL into a high-quality PDF file.

## How it works

Papermark renders decks as individually-signed CloudFront images that lazy-load one page at a time. You can't scrape the HTML or curl the image URLs — they're CORS-blocked and session-tied. This skill uses a bundled Playwright script that opens the deck in a headless browser, intercepts the CloudFront image responses as they arrive, navigates through every slide using keyboard/button input to trigger lazy loading, and compiles the images into a PDF.

## When to use this skill

Whenever a user shares a `papermark.com/view/` or `papermark.io/view/` URL and wants a PDF version.

## Workflow

### Step 1: Extract the URL and output path

Pull the Papermark URL from the user's message (or from the argument if invoked via `/papermark-to-pdf <url>`). It will look like:
```
https://www.papermark.com/view/<document-id>
https://www.papermark.io/view/<document-id>
```

For the output path: use the second argument if provided. If omitted, the script automatically derives a filename from the deck's page title (e.g. `Acme_Q3_Pitch.pdf`). If no title is available, it falls back to `deck.pdf`. Always tell the user the final output path once the script prints it.

### Step 2: Ensure dependencies are installed

Run this once per session if needed:
```bash
pip install playwright Pillow --break-system-packages -q 2>&1 | tail -1
playwright install chromium 2>&1 | tail -1
```

Playwright + Chromium is ~110 MB. The install takes about 30 seconds. If already installed, these commands return instantly.

### Step 3: Run the conversion script

```bash
python "<skill-dir>/scripts/papermark_to_pdf.py" \
  "<papermark-url>" \
  ["<output-path>.pdf"] \
  [--debug]
```

Both `output.pdf` and `--debug` are optional. The script handles everything: opening the page, intercepting signed CloudFront image responses, navigating through all slides via keyboard (ArrowRight) with button-click fallback, and compiling images into a landscape PDF. It prints per-page capture progress and exits 0 on success.

`--debug` logs every CloudFront URL intercepted, not just page images. Use it when diagnosing 0-image captures or unexpected URL patterns.

### Step 4: Report the result

Tell the user the file path, page count, and file size from the script's final output:
```
PDF saved: /path/to/deck.pdf  (N pages, X.X MB)
```

The script also prints a verification line confirming whether the captured page count matches the deck's reported slide count. Flag any mismatch to the user.

## Gotchas

These are hard-won lessons from building this skill. Each one is a dead end that looks promising but wastes time:

- **curl/wget won't work on the image URLs.** CloudFront signed URLs reject requests from outside the browser session, even with correct Referer and User-Agent headers. You'll get a 110-byte XML "Access denied" response.

- **JavaScript fetch() from the page context fails too.** The images are cross-origin (CloudFront), and the server doesn't send CORS headers. `fetch()` throws, and `no-cors` mode returns opaque responses you can't read.

- **Canvas toDataURL() is blocked.** Drawing a cross-origin image to a canvas taints it. `toDataURL()` returns a tiny blank image (98 chars of base64). Setting `crossOrigin = "anonymous"` on a new Image causes a load error because the server doesn't support CORS.

- **Scrolling doesn't trigger lazy loading.** Papermark hides non-current slides with a CSS `hidden` class on the parent container. IntersectionObserver never fires because the elements are `display:none`, not off-screen. You must navigate through the slides using keyboard or button input.

- **Position-based button detection is fragile.** The script previously found the "next" button by checking `box["x"] > 1400`. This breaks on any viewport change or layout tweak. The script now uses `ArrowRight` keyboard navigation first, with positional button-click as a fallback.

- **jsPDF from CDN is blocked.** Papermark's Content Security Policy blocks external script loading.

- **Each page has a unique CloudFront signature.** You can't extract one page's signed URL and swap the page number. Each `/page-N.jpeg` has its own cryptographic signature. The only way to get all signatures is to navigate to each page and let the viewer fetch them.

- **Some slides are PNG, not JPEG.** The format varies per slide. The script handles both automatically, converting RGBA/P-mode PNGs to RGB before PDF assembly.

- **The last "page" may be a Papermark promo slide.** Papermark sometimes appends an account-creation page not part of the deck. The script captures only pages intercepted from CloudFront image responses, so promo slides served differently are naturally excluded.

## Troubleshooting

- **Timeout during navigation**: Papermark may be slow or the URL may require authentication. Check that the link is publicly accessible (no email gate or password).
- **0 images captured**: The page structure may have changed. Check if `img[alt^="Page"]` still matches slide images, or if CloudFront URLs still contain `/page-`. Run with `--debug` to print every CloudFront URL intercepted and confirm the expected pattern.
- **Partial capture (fewer pages than expected)**: The script waits up to 2s per slide. For very slow connections, you can increase the `sleep` values in the script.
- **Playwright install fails**: Try `playwright install --with-deps chromium` to also install system dependencies.
