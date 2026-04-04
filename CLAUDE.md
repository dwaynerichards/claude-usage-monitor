# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Claude Code statusline plugin that displays quota usage, context window, token counts, and reset countdowns. It has zero external dependencies — stdlib only.

## Running tests

```bash
python tests/smoke_test.py
```

CI runs this on macOS, Linux, and Windows against Python 3.11. No test framework, no install step needed.

## Manual testing the statusline

```bash
printf '{"model":{"display_name":"Opus"},"context_window":{"used_percentage":25,"context_window_size":200000,"total_input_tokens":50000,"total_output_tokens":12000},"cost":{"total_cost_usd":0,"total_duration_ms":120000},"workspace":{"project_dir":"."}}' | python statusline.py
```

Empty stdin should print `Claude` and exit 0:
```bash
printf '' | python statusline.py
```

## Architecture

The plugin has three layers:

**Core script** (`statusline.py`) — reads Claude Code's session JSON from stdin, renders a two-line ANSI statusline. Quota data comes from `https://api.anthropic.com/api/oauth/usage`, fetched in a background thread and cached at `$TMPDIR/claude-sl-usage.json` for 5 minutes. Lock file `claude-sl-usage.lock` prevents concurrent fetches. The script must never crash visibly — all network/IO errors are silently swallowed.

**Platform launchers** (`statusline.sh`, `statusline.cmd`) — thin wrappers that locate the right Python binary and exec `statusline.py`. Stdin is passed through from Claude Code.

**Installer** (`install.py`) — copies the three runtime files to `~/.claude/plugins/claude-usage-monitor/`, patches `~/.claude/settings.json` with the `statusLine` command, and backs up the original settings. Shell (`install.sh`) and PowerShell (`install.ps1`) wrappers delegate to `install.py`.

## Key constraints

- **No external dependencies.** Do not import anything outside the Python stdlib.
- **Env vars are the configuration API.** All display toggles use `CQB_*` prefix (e.g., `CQB_TOKENS`, `CQB_BAR`). Defaults must not break existing configs.
- **Installer must preserve unknown settings.** `install.py` merges only `statusLine` into existing `settings.json`; all other keys must survive.
- **Smoke tests must pass on all three platforms.** When changing installer or launcher behavior, update `tests/smoke_test.py` accordingly.

## Auth

OAuth token is read from `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`, or from the `CLAUDE_CODE_OAUTH_TOKEN` env var override. Users who authenticated via API key (not browser OAuth) will see `no token` in the statusline.
