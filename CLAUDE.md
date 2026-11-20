# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

- No test suite, linter, or build step exists in this repo. Verifying a change means running `auto_login.py` against the live seller portal, which spends real boost slots — ask before doing that.
- Operational context (the ~7-day session expiry, setup on a new machine, why a systemd timer) lives in `README.md`; design notes for the script live in the docstrings and comments in `auto_login.py`.
