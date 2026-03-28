# Contributing to claude-usage-monitor

Thanks for your interest in contributing! Here's how to get started.

## Reporting issues

- Search [existing issues](https://github.com/aiedwardyi/claude-usage-monitor/issues) before opening a new one
- Include your OS, Python version, and launcher environment (PowerShell, cmd, bash, zsh)
- Paste the error output or a screenshot of the broken statusline

## Submitting changes

1. Fork the repo and create a branch from `main`
2. Make your changes — keep commits focused and descriptive
3. Test on your local Claude Code setup
4. Open a pull request against `main`

## Code style

- Python: follow PEP 8, keep functions short and well-named
- Shell: keep Unix launcher changes small and document platform-specific workarounds
- No additional dependencies — the plugin uses only the Python standard library

## What makes a good PR

- Solves one problem or adds one feature
- Includes a brief description of *why*, not just *what*
- Doesn't break existing configurations (env vars, settings.json format)
- Includes a smoke test update when installer or launcher behavior changes

## Questions?

Open an issue — happy to help.
