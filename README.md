# shopee auto-boost

Playwright script that logs into `seller.shopee.tw` and boosts (置頂推廣)
every eligible product listing on a recurring schedule (`shopee-boost.timer`,
every 4h5m). See `CLAUDE.md` for architecture details.

## Known issue: scheduled runs fail every ~7 days

**Symptom:** `shopee-boost.service` fails with:

```
Credentials submitted.
No terminal attached (running unattended) -- can't wait for a human to clear
a CAPTCHA/OTP step. Run this manually once to refresh the session, then the
scheduled runs will skip login again.
```

**Cause:** `storage_state.json` is just a Playwright-format dump of cookies
and localStorage -- Playwright itself imposes no expiry. The auth cookie
inside it has a fixed *Shopee server-side* expiry of about 7 days,
regardless of how often it's used.
When it expires, `auto_login.py` falls back to a headed login, which needs a
human to clear Shopee's slide-puzzle CAPTCHA and/or OTP step. Unattended
runs (systemd timer, no TTY) can't do that and exit with status 1.

Confirmed via `journalctl --user -u shopee-boost.service`: session saved
2026-09-09 22:33, first unattended failure 2026-09-17 00:48 (~7 days later),
then every run failed until a manual headed re-login.

Automating past this isn't viable: Shopee's login flow only offers OTP (no
TOTP/authenticator-app option), and OTP itself is gated behind a slide-to-
complete anti-bot CAPTCHA that has to be solved before the OTP channel is
even revealed. Scripting around that CAPTCHA would mean building automation
to evade Shopee's own anti-bot protection, which is out of scope here.

**Resolution:** a second timer, `shopee-session-check.timer`, runs
`check_session.py` once a day. It headlessly checks whether
`storage_state.json` is still valid and fires a desktop notification
(`notify-send`) only when it's expired, telling you to refresh it. No
notification means the session is still good.

When notified, refresh the session manually:

```
source .venv/bin/activate
python auto_login.py
```

Clear the CAPTCHA/OTP by hand when prompted (headed browser opens). Once
done, `storage_state.json` is refreshed and scheduled boost runs resume
normally for another ~7 days.

### Files involved

- `check_session.py` — the daily headless validity check
- `systemd/shopee-session-check.service` / `.timer` — runs it daily
- `systemd/shopee-boost.service` / `.timer` — the boost job (every 4h5m)

## Setup on a new machine

`.env` and `storage_state.json` are gitignored, so they have to be recreated:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/roachhuang/shopee ~/projects/shopee
cd ~/projects/shopee
uv sync
uv run playwright install --with-deps chromium
printf 'email=...\npassword=...\n' > .env   # fill in real credentials
uv run python auto_login.py                 # headed: clear CAPTCHA/OTP by hand
systemd/install.sh                          # install + start both timers
```

`install.sh` renders the unit templates in `systemd/` (replacing `@REPO@`
with this checkout's path) into `~/.config/systemd/user/` and enables the
timers. Re-run it if the repo moves.

User timers only run while you're logged in. To keep boosting after logout
or before login following a reboot, run `loginctl enable-linger "$USER"`.
