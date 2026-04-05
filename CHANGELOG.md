# Changelog

## v0.2.0

### Added
- `--version` flag for `statusline.py`
- `CQB_ASCII_BARS` env var for terminals where Unicode bar chars render incorrectly
- `--dry-run` flag for `install.py` to preview changes without writing files
- Auth error detection — expired OAuth tokens now show a clear re-auth message
- New smoke tests: no-token path, malformed cache, compact() and format_duration() helpers

### Changed
- Extra usage meter now visible whenever extra credits are consumed (previously required 5h >= 80%)
- "no token" message replaced with actionable "sign in with claude login" guidance
- Timestamp parser hardened for all ISO 8601 variants (fractional seconds, arbitrary tz offsets)

### Fixed
- Extra usage no longer shows `$0.00/$0.00` when limit is zero
- Installer now warns and overwrites non-dict `statusLine` values instead of aborting

## v0.1.2

### Changed
- Default to remaining % (fuel gauge) for all metrics - context, 5h, and 7d now all count down consistently. Set `CQB_REMAINING=0` to restore used % for quotas.

## v0.1.1

### Added
- Visual progress bar for 5h/7d quotas (on by default, disable with `CQB_BAR=0`)
- Clear `no token` message when OAuth credentials are missing instead of silent `--`

## v0.1.0

Initial release.

- 5h/7d quota tracking with color-coded percentages
- Context window usage gauge
- Token counts, reset countdowns, session duration
- One-command install for Windows, macOS, and Linux
- Configurable segments via environment variables
- `CQB_REMAINING` option to show remaining % instead of used %
