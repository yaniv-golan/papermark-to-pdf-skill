# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-14

### Changed
- Navigation now uses `ArrowRight` keyboard input as the primary slide-advance method, replacing fragile positional button detection (`box["x"] > 1400`) which broke on viewport changes
- Fallback button detection is now viewport-relative (uses `mid_x`/`mid_y`) instead of hard-coded pixel thresholds
- URL validation now recognizes both `papermark.com` and `papermark.io` domains
- Added stall detection: if no new images are captured after 3 keyboard presses, the script tries the click fallback; if stuck for 8 attempts, navigation stops gracefully
- Added progress percentage logging during navigation (`Captured N/M`)
- Added body click before keyboard navigation to ensure the viewer receives keyboard events
- Warning message when 0 slide images are found in the DOM now includes possible causes
- SKILL.md description updated to include `papermark.io` domain and clarify navigation strategy
- SKILL.md Gotchas section updated to explain why positional button detection was replaced
- SKILL.md Troubleshooting expanded with partial-capture guidance

## [1.0.0] - 2026-04-01

### Added
- Initial release
- Converts any public `papermark.com/view/` link to a multi-page PDF
- Playwright-based headless browser with CloudFront response interception
- Handles both JPEG and PNG slide formats (RGBA/P-mode auto-converted to RGB)
- Navigates slides via positional button detection
- Bundled `papermark_to_pdf.py` script with progress logging
- Comprehensive Gotchas section documenting CORS, canvas taint, and CSP dead ends
