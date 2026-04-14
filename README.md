# Papermark to PDF

[![Install in Claude Desktop](https://img.shields.io/badge/Install_in_Claude_Desktop-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://yaniv-golan.github.io/papermark-to-pdf-skill/static/install-claude-desktop.html)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Agent Skills Compatible](https://img.shields.io/badge/Agent_Skills-compatible-4A90D9)](https://agentskills.io)
[![Claude Code Plugin](https://img.shields.io/badge/Claude_Code-plugin-F97316)](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/plugins)
[![Cursor Plugin](https://img.shields.io/badge/Cursor-plugin-00D886)](https://cursor.com/docs/plugins)
[![Packaged with Skill Packager](https://img.shields.io/badge/Packaged_with-Skill_Packager-8B5CF6?style=flat-square)](https://github.com/yaniv-golan/skill-packager-skill)

Convert any Papermark shared deck link into a downloadable PDF — automatically, in one step.

Uses the open [Agent Skills](https://agentskills.io) standard. Works with Claude Desktop, Claude Code, Cursor, Codex CLI, Manus, and other compatible agents.

## What It Does

- Accepts any `papermark.com/view/` or `papermark.io/view/` URL
- Opens the deck in a headless browser and intercepts the signed CloudFront image responses
- Navigates through every slide using keyboard input to trigger lazy loading
- Compiles all captured images into a properly ordered, landscape PDF
- Reports the output path, page count, and file size when done

No manual steps. No copy-pasting image URLs. No CORS workarounds needed.

## Why a script?

Papermark renders each slide as a per-session signed CloudFront image. You can't download these with curl (session-tied), fetch() (CORS-blocked), or canvas extraction (tainted). The only reliable approach is browser-level response interception — which is what the bundled Playwright script does.

## Installation

### Claude Desktop

[![Install in Claude Desktop](https://img.shields.io/badge/Install_in_Claude_Desktop-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://yaniv-golan.github.io/papermark-to-pdf-skill/static/install-claude-desktop.html)

*— or install manually —*

1. Click **Customize** in the sidebar
2. Click **Browse Plugins**
3. Go to the **Personal** tab and click **+**
4. Choose **Add marketplace**
5. Type `yaniv-golan/papermark-to-pdf-skill` and click **Sync**

### Claude Code (CLI)

```bash
claude plugin marketplace add https://github.com/yaniv-golan/papermark-to-pdf-skill
claude plugin install papermark-to-pdf@papermark-to-pdf-marketplace
```

Or from within a Claude Code session:

```
/plugin marketplace add yaniv-golan/papermark-to-pdf-skill
/plugin install papermark-to-pdf@papermark-to-pdf-marketplace
```

### Any Agent (npx)

Works with Claude Code, Cursor, Copilot, Windsurf, and [40+ other agents](https://github.com/vercel-labs/skills):

```bash
npx skills add yaniv-golan/papermark-to-pdf-skill
```

### Cursor

1. Open **Cursor Settings**
2. Paste `https://github.com/yaniv-golan/papermark-to-pdf-skill` into the **Search or Paste Link** box

### Claude.ai (Web)

> **Warning:** This skill requires Playwright and a headless Chromium browser, which are not available in Claude.ai's web sandbox. Use Claude Desktop or Claude Code instead.

1. Download [`papermark-to-pdf.zip`](https://github.com/yaniv-golan/papermark-to-pdf-skill/releases/latest/download/papermark-to-pdf.zip)
2. Click **Customize** in the sidebar → **Skills** → **+** → **Upload a skill**

### Manus

1. Download [`papermark-to-pdf.zip`](https://github.com/yaniv-golan/papermark-to-pdf-skill/releases/latest/download/papermark-to-pdf.zip)
2. Go to **Settings** → **Skills** → **+ Add** → **Upload**
3. Upload the zip

### ChatGPT

> **Note:** ChatGPT Skills are currently in beta, available on Business, Enterprise, Edu, Teachers, and Healthcare plans only.
> **Warning:** This skill requires Playwright/Chromium which is not available in ChatGPT's execution sandbox. It will not work in ChatGPT.

### Codex CLI

```
$skill-installer https://github.com/yaniv-golan/papermark-to-pdf-skill
```

Or install manually:

1. Download [`papermark-to-pdf.zip`](https://github.com/yaniv-golan/papermark-to-pdf-skill/releases/latest/download/papermark-to-pdf.zip)
2. Extract the `papermark-to-pdf/` folder to `~/.codex/skills/`

### Other Tools (Windsurf, etc.)

Download [`papermark-to-pdf.zip`](https://github.com/yaniv-golan/papermark-to-pdf-skill/releases/latest/download/papermark-to-pdf.zip) and extract the `papermark-to-pdf/` folder to:

- **Project-level**: `.agents/skills/` in your project root
- **User-level**: `~/.agents/skills/`

## Prerequisites

The skill installs its own dependencies on first run, but your machine needs:

- Python 3.8+
- pip

The script will automatically run `pip install playwright Pillow` and `playwright install chromium` (~110 MB, one-time download).

## Usage

The skill auto-activates when you share a Papermark link and ask for a PDF. Examples:

```
Here's the deck we got from the vendor: https://www.papermark.com/view/abc123 — can you save it as a PDF?
```

```
Download this Papermark link as a PDF and put it on my Desktop: https://papermark.io/view/xyz789
```

```
https://www.papermark.com/view/def456 → PDF please
```

The skill will install dependencies if needed, run the conversion, and report the output path.

## License

MIT
