#!/usr/bin/env python3
"""
Claude Code statusline with 5h/7d quota tracking.

Shows: model, context gauge, tokens, git branch, 5h remaining%, 7d remaining%,
pace indicator, and reset countdown.

Designed for Claude Code on Windows, macOS, and Linux. Caches API responses to
the system temp directory for 5 minutes.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import threading
from pathlib import Path

__version__ = "0.2.0"

# --version flag: print version and exit before reading stdin.
# Claude Code never passes args to the statusline command, so this is safe.
if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print(__version__)
    sys.exit(0)

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# ── Configuration (env vars) ─────────────────────────────────────
# All display toggles use the CQB_ prefix (Claude Quota Bar).
# Set in your shell profile or in ~/.claude/settings.json under "env".
# Values: "1" = show, "0" = hide.
#
# CQB_CONTEXT_SIZE  (default 0) — append "of 200K" label after context gauge
# CQB_TOKENS        (default 1) — show ↑input ↓output token counts
# CQB_PACE          (default 0) — show ahead/behind pace indicator vs linear burn
# CQB_RESET         (default 1) — show quota reset countdowns (e.g., "(1h)")
# CQB_DURATION      (default 1) — show session wall-clock duration
# CQB_BRANCH        (default 1) — show git branch name after project
# CQB_COST          (default 0) — show cumulative session cost in USD
# CQB_REMAINING     (default 1) — show remaining % (fuel gauge); 0 = used %
# CQB_BAR           (default 1) — show ▰▱ visual progress bars for quotas
# CQB_ASCII_BARS    (default 0) — use # and - instead of ▰ and ▱ (for terminals
#                                  where Unicode block chars render as boxes)
SHOW_CONTEXT_SIZE = os.environ.get("CQB_CONTEXT_SIZE", "0") == "1"
SHOW_TOKENS = os.environ.get("CQB_TOKENS", "1") == "1"
SHOW_PACE = os.environ.get("CQB_PACE", "0") == "1"
SHOW_RESET = os.environ.get("CQB_RESET", "1") == "1"
SHOW_DURATION = os.environ.get("CQB_DURATION", "1") == "1"
SHOW_BRANCH = os.environ.get("CQB_BRANCH", "1") == "1"
SHOW_COST = os.environ.get("CQB_COST", "0") == "1"
SHOW_REMAINING = os.environ.get("CQB_REMAINING", "1") == "1"
SHOW_BAR = os.environ.get("CQB_BAR", "1") == "1"
ASCII_BARS = os.environ.get("CQB_ASCII_BARS", "0") == "1"

# Bar characters — switchable for terminal compatibility
BAR_FULL = "#" if ASCII_BARS else "\u25b0"   # ▰ or #
BAR_EMPTY = "-" if ASCII_BARS else "\u25b1"  # ▱ or -

# ── Read stdin ──────────────────────────────────────────────────
raw = sys.stdin.read().strip()
if not raw:
    print("Claude")
    sys.exit(0)

try:
    d = json.loads(raw)
except json.JSONDecodeError:
    print("Claude")
    sys.exit(0)

# ── ANSI colors ─────────────────────────────────────────────────
C = "\033[36m"   # cyan
G = "\033[32m"   # green
Y = "\033[33m"   # yellow
R = "\033[31m"   # red
D = "\033[2m"    # dim
N = "\033[0m"    # reset


def color_pct(used_pct):
    """Color based on how much quota is USED (high = bad)."""
    if used_pct >= 90:
        return R
    if used_pct >= 70:
        return Y
    return G


# ── Parse session data ──────────────────────────────────────────
model = "Opus"
try:
    model = d["model"]["display_name"]
except (KeyError, TypeError):
    pass

ctx_pct_used = 0
ctx_size = 0
try:
    ctx_pct_used = int(d["context_window"]["used_percentage"] or 0)
    ctx_size = int(d["context_window"]["context_window_size"] or 0)
except (KeyError, TypeError, ValueError):
    pass

in_tok = 0
out_tok = 0
try:
    in_tok = d["context_window"]["total_input_tokens"] or 0
except (KeyError, TypeError):
    pass
try:
    out_tok = d["context_window"]["total_output_tokens"] or 0
except (KeyError, TypeError):
    pass

cost_usd = 0.0
duration_ms = 0
try:
    cost_usd = float(d["cost"]["total_cost_usd"] or 0)
except (KeyError, TypeError, ValueError):
    pass
try:
    duration_ms = int(d["cost"]["total_duration_ms"] or 0)
except (KeyError, TypeError, ValueError):
    pass

proj_dir = ""
proj_name = ""
try:
    proj_dir = d["workspace"]["project_dir"] or ""
    proj_name = os.path.basename(proj_dir)
except (KeyError, TypeError):
    pass

# ── Git branch ──────────────────────────────────────────────────
branch = ""
cwd = os.getcwd()
candidate_dirs = []
if proj_dir:
    candidate_dirs.append(proj_dir)
if cwd and cwd not in candidate_dirs:
    candidate_dirs.append(cwd)

for try_dir in candidate_dirs:
    if not try_dir:
        continue
    try:
        r = subprocess.run(
            ["git", "-C", try_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            branch = r.stdout.strip()
            if not proj_name:
                proj_name = os.path.basename(try_dir)
            break
    except Exception:
        pass

# ── Helpers ─────────────────────────────────────────────────────
def compact(n):
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}m".replace(".0m", "m")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".0k", "k")
    return str(int(n))


def format_duration(ms):
    if ms >= 3_600_000:
        return f"{ms // 3_600_000}h{(ms // 60_000) % 60}m"
    if ms >= 60_000:
        return f"{ms // 60_000}m{(ms // 1000) % 60}s"
    return f"{ms // 1000}s"


def format_reset(minutes):
    """Format reset countdown."""
    if minutes is None:
        return ""
    m = int(minutes)
    if m >= 1440:
        return f" {D}({m // 1440}d){N}"
    if m >= 60:
        return f" {D}({m // 60}h){N}"
    return f" {D}({m}m){N}"



def used_pct_str(used_pct):
    """Format used or remaining % with color."""
    if used_pct is None or used_pct == "--":
        return "--"
    used = int(used_pct)
    c = color_pct(used)
    val = 100 - used if SHOW_REMAINING else used
    if SHOW_BAR:
        filled = round(min(100, max(0, val)) / 100.0 * 5)
        filled_chars = BAR_FULL * filled
        empty_chars = BAR_EMPTY * (5 - filled)
        bar = f"{c}{filled_chars}{empty_chars}{N} "
    else:
        bar = ""
    return f"{bar}{c}{val}%{N}"


def pace_indicator(used_pct, remain_min, window_min):
    """Show pace: positive = ahead (green), negative = over pace (red). Suppress within +/-10%."""
    if used_pct is None or remain_min is None:
        return ""
    try:
        used = int(used_pct)
        rmin = int(remain_min)
    except (ValueError, TypeError):
        return ""
    if rmin > window_min:
        return ""
    elapsed = window_min - rmin
    if elapsed <= 0:
        return ""
    expected = (elapsed * 100) // window_min
    delta = expected - used
    if delta > 10:
        return f" {G}+{delta}%{N}"
    if delta < -10:
        return f" {R}{delta}%{N}"
    return ""


# ── Quota API ───────────────────────────────────────────────────
CACHE_FILE = os.path.join(tempfile.gettempdir(), "claude-sl-usage.json")
CACHE_TTL = 300  # 5 minutes
LOCK_FILE = os.path.join(tempfile.gettempdir(), "claude-sl-usage.lock")


def get_oauth_token():
    """Read OAuth token from Claude Code's credential store."""
    # Env var override
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if tok:
        return tok
    # Credentials file (Linux / older installs)
    cred_path = Path.home() / ".claude" / ".credentials.json"
    if cred_path.exists():
        try:
            creds = json.loads(cred_path.read_text(encoding="utf-8"))
            tok = creds.get("claudeAiOauth", {}).get("accessToken")
            if tok:
                return tok
        except Exception:
            pass
    # macOS Keychain (Claude Code stores credentials here on macOS)
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            creds = json.loads(result.stdout.strip())
            tok = creds.get("claudeAiOauth", {}).get("accessToken")
            if tok:
                return tok
    except Exception:
        pass
    return None


def fetch_usage_sync():
    """Call Anthropic usage API and write cache. Run in background thread."""
    try:
        token = get_oauth_token()
        if not token:
            return

        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "Content-Type": "application/json",
            },
        )

        cache_data = None
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            def parse_reset_minutes(iso_str):
                """Parse an ISO 8601 timestamp and return minutes until that time.

                Handles Z suffix, fractional seconds, and arbitrary timezone offsets.
                Uses fromisoformat (Python 3.11+ handles Z natively; older versions
                need the Z → +00:00 normalization).
                """
                if not iso_str:
                    return None
                try:
                    from datetime import datetime, timezone

                    s = iso_str
                    # Normalize Z suffix — Python < 3.11 doesn't accept Z in fromisoformat
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"

                    # Strip fractional seconds (e.g., ".123456") while preserving tz offset.
                    # Fractional seconds sit between the seconds digit and the tz sign.
                    if "." in s:
                        dot_idx = s.index(".")
                        # Find the start of the timezone offset after the dot
                        tz_start = None
                        for i in range(dot_idx + 1, len(s)):
                            if s[i] in ("+", "-"):
                                tz_start = i
                                break
                        if tz_start is not None:
                            s = s[:dot_idx] + s[tz_start:]
                        else:
                            # No tz offset after fractional seconds — just truncate
                            s = s[:dot_idx]

                    dt = datetime.fromisoformat(s)
                    now = datetime.now(timezone.utc)
                    return max(0, int((dt - now).total_seconds() / 60))
                except Exception:
                    return None

            cache_data = {
                "five_hour_used": data.get("five_hour", {}).get("utilization", 0),
                "seven_day_used": data.get("seven_day", {}).get("utilization", 0),
                "five_hour_reset_min": parse_reset_minutes(data.get("five_hour", {}).get("resets_at")),
                "seven_day_reset_min": parse_reset_minutes(data.get("seven_day", {}).get("resets_at")),
                "extra_enabled": data.get("extra_usage", {}).get("is_enabled", False),
                "extra_used": data.get("extra_usage", {}).get("used_credits", 0),
                "extra_limit": data.get("extra_usage", {}).get("monthly_limit", 0),
                "fetched_at": time.time(),
            }
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # Token expired or revoked — sentinel tells renderer to prompt re-auth
                cache_data = {"auth_error": True, "fetched_at": time.time()}
            # Other HTTP errors: leave cache unchanged (will retry next cycle)

        if cache_data is not None:
            tmp = CACHE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(cache_data, f)
            os.replace(tmp, CACHE_FILE)

    except Exception:
        pass  # Intentional: statusline must never fail visibly
    finally:
        try:
            os.unlink(LOCK_FILE)
        except OSError:
            pass


_fetch_thread = None

def read_cached_usage():
    """Read cached usage data, trigger background refresh if stale."""
    global _fetch_thread
    cache = None
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
        except Exception:
            pass

    # Check if cache is stale
    now = time.time()
    fetched_at = (cache or {}).get("fetched_at", 0)
    is_stale = (now - fetched_at) > CACHE_TTL

    if is_stale:
        # Try to acquire lock (non-blocking)
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            # Fetch in background thread; joined at end of script
            t = threading.Thread(target=fetch_usage_sync)
            t.start()
            _fetch_thread = t
        except FileExistsError:
            # Another process is fetching; check if lock is stale (>30s)
            try:
                lock_age = now - os.path.getmtime(LOCK_FILE)
                if lock_age > 30:
                    os.unlink(LOCK_FILE)
            except OSError:
                pass

    if cache:
        # Auth error sentinel — token expired/revoked
        if cache.get("auth_error"):
            return {"auth_error": True}

        # Adjust reset minutes for time elapsed since fetch
        elapsed_min = (now - cache.get("fetched_at", now)) / 60
        r5 = cache.get("five_hour_reset_min")
        r7 = cache.get("seven_day_reset_min")
        if r5 is not None:
            r5 = max(0, int(r5 - elapsed_min))
        if r7 is not None:
            r7 = max(0, int(r7 - elapsed_min))
        return {
            "u5": cache.get("five_hour_used"),
            "u7": cache.get("seven_day_used"),
            "r5": r5,
            "r7": r7,
            "extra_enabled": cache.get("extra_enabled", False),
            "extra_used": cache.get("extra_used", 0),
            "extra_limit": cache.get("extra_limit", 0),
        }

    return None


# ── Build output ────────────────────────────────────────────────
SEP = " \u2502 "  # │
DIAMOND = "\u25c6"  # ◆

# Context gauge (5 blocks)
ctx_remaining = 100 - ctx_pct_used
filled = round(min(100, max(0, ctx_remaining)) / 100.0 * 5)
gauge = BAR_FULL * filled + BAR_EMPTY * (5 - filled)

# Context size label
if ctx_size >= 1_000_000:
    ctx_label = f"{ctx_size // 1_000_000}M"
else:
    ctx_label = f"{ctx_size // 1000}K"

# Line 1: model, project, branch
line1_parts = [f"{C}{DIAMOND} {model}{N}"]

if proj_name:
    loc = f"{proj_name}/{branch}" if (branch and SHOW_BRANCH) else proj_name
    if len(loc) > 40:
        loc = loc[:39] + "\u2026"
    line1_parts.append(loc)

line1 = SEP.join(line1_parts)

# Line 2: context gauge, quota, duration
ctx_color = color_pct(ctx_pct_used)
ctx_str = f"{ctx_color}{gauge}{N} {ctx_remaining}%"
if SHOW_CONTEXT_SIZE:
    ctx_str += f" of {ctx_label}"
line2_parts = [ctx_str]

# Token counts
if SHOW_TOKENS and (in_tok or out_tok):
    line2_parts.append(f"\u2191{compact(in_tok)} \u2193{compact(out_tok)}")

# Quota
usage = read_cached_usage()
if usage and usage.get("auth_error"):
    # Token exists but is expired — give the user a clear action
    line2_parts.append(f"{D}quota: token expired, run claude login{N}")
elif usage:
    u5 = usage["u5"]
    u7 = usage["u7"]
    r5 = usage["r5"]
    r7 = usage["r7"]

    pace5 = pace_indicator(u5, r5, 300) if SHOW_PACE else ""
    pace7 = pace_indicator(u7, r7, 10080) if SHOW_PACE else ""
    reset5 = format_reset(r5) if SHOW_RESET else ""
    reset7 = format_reset(r7) if (SHOW_RESET and u7 is not None and int(u7) >= 70) else ""

    line2_parts.append(f"5h: {used_pct_str(u5)}{pace5}{reset5}")
    line2_parts.append(f"7d: {used_pct_str(u7)}{pace7}{reset7}")

    # Extra usage — show when 5h quota is nearly exhausted AND a real limit exists.
    # The API returns credits in cents, so we divide by 100 to get USD.
    extra_enabled = usage["extra_enabled"]
    extra_limit = int(usage["extra_limit"])
    # Show extra usage whenever it's enabled and the user has consumed any credits,
    # not just when 5h quota is near exhaustion — users need visibility into spend.
    if extra_enabled and extra_limit > 0 and int(usage.get("extra_used", 0)) > 0:
        extra_used_usd = int(usage["extra_used"]) / 100
        extra_limit_usd = extra_limit / 100
        line2_parts.append(f"${extra_used_usd:.2f}/${extra_limit_usd:.2f}")
else:
    if not get_oauth_token():
        # API key users don't have OAuth tokens, so quota data is unavailable.
        # Show a single clear label instead of two confusing "no token" segments.
        line2_parts.append(f"{D}quota: sign in with claude login{N}")
    else:
        # Token exists but cache hasn't populated yet (first run or stale cache).
        line2_parts.append(f"5h: {D}--{N}")
        line2_parts.append(f"7d: {D}--{N}")

# Cost
if SHOW_COST and cost_usd > 0:
    line2_parts.append(f"{D}${cost_usd:.2f}{N}")

# Duration
if SHOW_DURATION:
    line2_parts.append(f"{D}{format_duration(duration_ms)}{N}")

line2 = SEP.join(line2_parts)

print(line1)
print(line2)

# Wait for background fetch to finish (max 8s) so cache gets written
if _fetch_thread is not None:
    _fetch_thread.join(timeout=8)
