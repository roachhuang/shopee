"""
Login to the Shopee seller portal (auto-filling credentials from .env,
pausing only for CAPTCHA / OTP / 2FA) and boost every eligible product via
each row's 更多 -> 點我置頂推廣 action.

If a saved session already exists and is still valid, login is skipped
entirely and it goes straight to boosting -- safe to run on a recurring
schedule (every 4h5m) without a human present.

Boost slots are a limited, account-wide quota. Once exhausted, a row's
點我置頂推廣 item is replaced by a live HH:MM:SS countdown instead of
being clickable. This script only clicks rows where the option is still
available and leaves locked / not-offered rows alone.

Usage:
    source .venv/bin/activate
    python auto_login.py

Exit behavior:
    Prints a one-line summary, e.g.:
        Boosted 2, locked 1, no option 2, 0 errors.
"""

import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ENV_FILE = Path(__file__).parent / ".env"
STATE_FILE = Path(__file__).parent / "storage_state.json"
PRODUCT_LIST_URL = "https://seller.shopee.tw/portal/product/list/live/all"

BOOST_TEXT = "點我置頂推廣"
COUNTDOWN_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def load_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        key = key.strip()
        value = raw_value.strip().strip("'\"")
        values[key] = value
    return values


def is_logged_in(page) -> bool:
    # Careful: a successful login redirects to a URL containing
    # "is_from_login=true", so a naive "login" substring check false-
    # positives right after a real login succeeds. Check the host instead.
    return "accounts.shopee.tw" not in page.url.lower()


def do_login(page, email: str, password: str) -> bool:
    page.goto(PRODUCT_LIST_URL)
    page.wait_for_load_state("networkidle")

    # Dismiss the language-select dialog if it appears (switching to
    # English triggers a full page reload, so wait for that to settle).
    try:
        page.get_by_role("button", name="English").click(timeout=8000)
        page.wait_for_load_state("networkidle")
    except PWTimeout:
        pass

    username = page.get_by_role("textbox", name=re.compile("Phone|Email|電話號碼"))
    password_box = page.get_by_role("textbox", name=re.compile("Password|密碼"))
    username.wait_for(timeout=15000)
    username.fill(email)
    password_box.fill(password)
    page.get_by_role("button", name=re.compile("^Log ?[Ii]n$|^登入$")).click()

    print("\nCredentials submitted.")
    if not sys.stdin.isatty():
        print("No terminal attached (running unattended) -- can't wait for a human "
              "to clear a CAPTCHA/OTP step. Run this manually once to refresh the "
              "session, then the scheduled runs will skip login again.")
        return False
    print("If Shopee shows a CAPTCHA / OTP / 2FA step, complete it by hand now.")
    print("Once you can see your product list, come back here and press Enter.")
    input()

    # The post-login redirect off accounts.shopee.tw can lag a beat behind
    # you pressing Enter -- poll briefly instead of checking the URL once.
    for _ in range(10):
        if is_logged_in(page):
            return True
        page.wait_for_timeout(500)

    print(f"Still looks like a login page (current URL: {page.url}). "
          "Finish logging in, then re-run this script.")
    return False


def close_stray_menu(page):
    """Best-effort cleanup: dismiss any dropdown/dialog left open after an
    error, so it doesn't block clicks on the next row."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    try:
        page.mouse.click(1, 1)
    except Exception:
        pass


def boost_row(page, more_button) -> str:
    """
    Open one product row's 更多 menu and boost it if 點我置頂推廣 is
    available. Returns "boosted", "failed" (click didn't take effect),
    "locked" (a countdown is showing in its place), or "no_option" (the
    item isn't offered at all -- either the product is ineligible, e.g.
    out-of-stock, or it's already mid-cooldown itself and Shopee just
    drops the entry from the menu instead of showing a countdown).
    """
    more_button.click()
    # Closed dropdowns stay in the DOM (hidden, not removed), so after a
    # few rows there are several .more-dropdown-menu elements -- always
    # target the most recently opened one.
    menu = page.locator(".more-dropdown-menu").last
    try:
        menu.wait_for(state="visible", timeout=5000)
    except PWTimeout:
        return "no_option"

    boost_item = menu.get_by_text(BOOST_TEXT, exact=True)
    if boost_item.count() > 0:
        boost_item.first.click()
        # Some accounts show a confirm step after clicking -- click it if
        # it appears, scoped to whatever dialog/popup just opened so we
        # don't hit an unrelated same-named button elsewhere on the page.
        try:
            confirm_scope = page.locator("[role=dialog], .eds-modal, .more-dropdown-menu").last
            confirm_scope.get_by_role("button", name=re.compile("確認|確定")).click(timeout=3000)
        except PWTimeout:
            pass

        # Verify it actually took effect: reopen the menu and check that
        # the item switched to a countdown instead of still offering the
        # boost action.
        page.wait_for_timeout(500)
        more_button.click()
        try:
            menu.wait_for(state="visible", timeout=3000)
            succeeded = menu.get_by_text(COUNTDOWN_RE).count() > 0
        except PWTimeout:
            succeeded = True  # menu didn't reopen (already closed) -- assume it applied
        more_button.click()
        return "boosted" if succeeded else "failed"

    has_countdown = menu.get_by_text(COUNTDOWN_RE).count() > 0
    more_button.click()  # toggle the menu closed again; nothing was selected
    return "locked" if has_countdown else "no_option"


def go_to_next_page(page) -> bool:
    """
    Try to advance pagination. Returns True if it moved to a new page,
    False if there's no next page (or pagination wasn't found at all).
    """
    next_button = page.get_by_role("button", name="Next")
    if next_button.count() == 0:
        next_button = page.locator("button[aria-label='Next page' i], .pagination-next, [class*='next']")
    if next_button.count() == 0:
        return False

    btn = next_button.first
    if not btn.is_enabled():
        return False

    btn.click()
    page.wait_for_load_state("networkidle")
    return True


def boost_all(page) -> tuple[int, int, int, int]:
    boosted = locked = no_option = errors = 0

    while True:
        more_buttons = page.get_by_role("button", name="更多", exact=True)
        count = more_buttons.count()

        for i in range(count):
            try:
                result = boost_row(page, more_buttons.nth(i))
                if result == "boosted":
                    boosted += 1
                elif result == "locked":
                    locked += 1
                elif result == "no_option":
                    no_option += 1
                else:  # "failed"
                    errors += 1
                page.wait_for_timeout(500)  # brief pause between rows
            except Exception:
                errors += 1
                close_stray_menu(page)

        if not go_to_next_page(page):
            break

    return boosted, locked, no_option, errors


def main():
    env = load_env(ENV_FILE)
    email = env.get("email")
    password = env.get("password")
    if not email or not password:
        print(f"Missing email/password in {ENV_FILE}")
        sys.exit(1)

    with sync_playwright() as p:
        # Quick headless check first: if a saved session is still valid,
        # skip login entirely and go straight to boosting.
        if STATE_FILE.exists():
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(storage_state=str(STATE_FILE))
                page = context.new_page()
                page.goto(PRODUCT_LIST_URL)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    pass
                session_ok = is_logged_in(page)
            except Exception:
                print("Saved session file is unreadable/corrupted -- logging in again.")
                session_ok = False

            if session_ok:
                print("Existing session still valid -- skipping login.")
                boosted, locked, no_option, errors = boost_all(page)
                browser.close()
                print(f"Boosted {boosted}, locked {locked}, no option {no_option}, {errors} errors.")
                return

            browser.close()
            print("Saved session expired -- logging in again.")

        # Fall back to a real, headed login (a human may need to clear a
        # CAPTCHA / OTP / 2FA step).
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        if not do_login(page, email, password):
            browser.close()
            sys.exit(1)

        context.storage_state(path=str(STATE_FILE))
        print(f"Session saved to {STATE_FILE}.")

        boosted, locked, no_option, errors = boost_all(page)
        browser.close()
        print(f"Boosted {boosted}, locked {locked}, no option {no_option}, {errors} errors.")


if __name__ == "__main__":
    main()
