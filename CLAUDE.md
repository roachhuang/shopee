# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Single-script Playwright automation that logs into the Shopee Taiwan seller portal (`seller.shopee.tw`) and boosts (置頂推廣) every eligible product listing via each row's `更多` -> `點我置頂推廣` menu action. Designed to run unattended on a recurring schedule (every 4h5m) once a valid session exists.

## Commands

```
uv sync                                   # create/update .venv from pyproject.toml + uv.lock
.venv/bin/playwright install --with-deps chromium   # first time only
source .venv/bin/activate
python auto_login.py
```

No test suite, linter, or build step exists in this repo.

## Architecture

- `auto_login.py` — the entire application. Flow: `main()` tries a headless run with the saved session (`storage_state.json`) first; if that's invalid/missing it falls back to a headed `do_login()` that pauses on a TTY for a human to clear CAPTCHA/OTP/2FA, then saves a fresh `storage_state.json`. Either path ends by calling `boost_all()`, which paginates the product list and calls `boost_row()` per row.
- `.env` — `email` / `password` credentials, loaded by the hand-rolled `load_env()` (no `python-dotenv` dependency).
- `systemd/` — user unit templates (`@REPO@` placeholder) for the boost timer (every 4h5m) and the daily `check_session.py` timer; `systemd/install.sh` renders them into `~/.config/systemd/user/` and enables them.
- `storage_state.json` — Playwright storage state (cookies/session) persisted between runs so login can be skipped when still valid.
- Login detection (`is_logged_in`) checks the URL host (`accounts.shopee.tw`) rather than doing a substring match on "login", because the post-login redirect URL itself contains `is_from_login=true` and would false-positive.
- Boost slots are a limited, account-wide quota: once exhausted, Shopee replaces a row's boost menu item with a live countdown instead of leaving it clickable. `boost_row()` returns one of `"boosted"`, `"failed"`, `"locked"`, or `"no_option"` and only acts on rows where the boost option is actually present.
- Closed dropdown menus stay in the DOM (hidden, not removed) rather than being removed, so selectors always target `.more-dropdown-menu` via `.last` to hit the most recently opened one.
- Running unattended (`not sys.stdin.isatty()`) short-circuits `do_login()` after submitting credentials rather than blocking on `input()` for a CAPTCHA/OTP step — the run must be done headed once manually to refresh the session before scheduled runs work again.
