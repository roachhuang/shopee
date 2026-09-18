"""
Headless check of whether storage_state.json still holds a valid Shopee
seller session. Sends a desktop notification (notify-send) only when the
session has expired, so you know to run `python auto_login.py` headed
before the next scheduled boost run fails.

Usage:
    source .venv/bin/activate
    python check_session.py
"""

import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

STATE_FILE = Path(__file__).parent / "storage_state.json"
PRODUCT_LIST_URL = "https://seller.shopee.tw/portal/product/list/live/all"


def is_logged_in(page) -> bool:
    return "accounts.shopee.tw" not in page.url.lower()


def notify(title: str, body: str) -> None:
    try:
        subprocess.run(["notify-send", title, body], check=False)
    except FileNotFoundError:
        print(f"{title}: {body}")


def main() -> None:
    if not STATE_FILE.exists():
        notify("Shopee session missing", "storage_state.json not found -- run auto_login.py headed.")
        return

    with sync_playwright() as p:
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
            session_ok = False
        browser.close()

    if not session_ok:
        notify(
            "Shopee session expired",
            "Run: cd ~/projects/shopee && source .venv/bin/activate && python auto_login.py",
        )


if __name__ == "__main__":
    main()
