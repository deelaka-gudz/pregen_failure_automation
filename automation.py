import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from dotenv import load_dotenv
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DOTENV_PATH = Path(__file__).resolve().with_name(".env")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y"}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _log_info(debug: bool, message: str) -> None:
    if debug:
        print(f"[INFO] {message}")


def _log_step(step: str) -> None:
    print(f"[DONE] {step}")


def _wait_for_network_idle(page: Page, timeout_ms: int = 10000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass


def _click_first_visible(
    locators: Sequence[Locator],
    description: str,
    timeout_ms: int = 5000,
) -> None:
    last_error: Optional[Exception] = None
    for locator in locators:
        try:
            locator.first.wait_for(state="visible", timeout=timeout_ms)
            locator.first.click(timeout=timeout_ms)
            return
        except (PlaywrightTimeoutError, PlaywrightError) as error:
            last_error = error
            continue
    raise RuntimeError(f"Could not click {description}.") from last_error


def _fill_first_visible(
    locators: Sequence[Locator],
    value: str,
    description: str,
    timeout_ms: int = 5000,
) -> Locator:
    last_error: Optional[Exception] = None
    for locator in locators:
        try:
            field = locator.first
            field.wait_for(state="visible", timeout=timeout_ms)
            field.click(timeout=timeout_ms)
            field.fill(value, timeout=timeout_ms)
            field.dispatch_event("input", timeout=timeout_ms)
            field.dispatch_event("change", timeout=timeout_ms)
            actual_value = field.input_value(timeout=timeout_ms)
            if actual_value != value:
                field.click(timeout=timeout_ms)
                field.press("Control+A", timeout=timeout_ms)
                field.type(value, delay=25, timeout=timeout_ms)
                field.dispatch_event("input", timeout=timeout_ms)
                field.dispatch_event("change", timeout=timeout_ms)
                actual_value = field.input_value(timeout=timeout_ms)
            if actual_value != value:
                raise RuntimeError(
                    f"Filled {description}, but the field value did not match."
                )
            return field
        except PlaywrightTimeoutError as error:
            last_error = error
            continue
    raise RuntimeError(f"Could not find {description}.") from last_error


def _click_pregen_failure(page: Page) -> None:
    tile = page.locator(
        ".status.loadthis",
        has=page.locator("#status_id_3009"),
    ).filter(has_text=re.compile(r"\bPreGen Failure\b", re.I))

    _click_first_visible(
        [
            tile,
            page.locator("#status_id_3009").locator("..").locator(".."),
            page.get_by_text(re.compile(r"\bPreGen Failure\b", re.I)).locator(".."),
        ],
        "PreGen Failure status",
    )
    page.wait_for_load_state("domcontentloaded")
    _wait_for_network_idle(page)


def _select_all_orders_on_page(page: Page) -> None:
    checkbox = page.locator("input.check-all-on-page.processible[type='checkbox']")
    checkbox.first.wait_for(state="visible", timeout=5000)
    if not checkbox.first.is_checked(timeout=5000):
        checkbox.first.click(timeout=5000)


def _open_bulk_action_dropdown(page: Page) -> None:
    dropdown = page.locator(
        ".custom-dropdown[data-dropdown='bulk-action']",
        has=page.locator("button.custom-dropdown__trigger"),
    )
    _click_first_visible(
        [
            dropdown.locator("button.custom-dropdown__trigger"),
            page.get_by_role("button", name=re.compile(r"Select Bulk Action", re.I)),
        ],
        "Select Bulk Action dropdown",
    )
    dropdown.locator(".custom-dropdown__content").first.wait_for(
        state="visible",
        timeout=5000,
    )


def _select_set_shipping_bulk_action(page: Page) -> None:
    bulk_action = page.locator("select[name='bulk_action']")
    bulk_action.first.wait_for(state="visible", timeout=5000)
    bulk_action.first.select_option("set_shipping", timeout=5000)
    page.locator("#shippingMethodRequested").first.wait_for(
        state="visible",
        timeout=5000,
    )


class LoginFlow:
    def __init__(self, page: Page, config: Any):
        self.page = page
        self.config = config

    def open(self) -> None:
        self.page.goto(self.config.helm_url, wait_until="load")
        _wait_for_network_idle(self.page)
        self.page.wait_for_timeout(1000)

    def fill_credentials(self) -> None:
        email_field = _fill_first_visible(
            [
                self.page.get_by_label("Email", exact=False),
                self.page.get_by_placeholder(re.compile("email", re.I)),
                self.page.locator("input[type='email']"),
                self.page.locator("input[name*='email' i]"),
            ],
            self.config.email,
            "email input",
        )

        password_field = _fill_first_visible(
            [
                self.page.get_by_label("Password", exact=False),
                self.page.get_by_placeholder(re.compile("password", re.I)),
                self.page.locator("input[type='password']"),
                self.page.locator("input[name*='password' i]"),
            ],
            self.config.password,
            "password input",
        )
        _log_info(
            self.config.debug,
            "Helm login fields filled: "
            f"email={bool(email_field.input_value())}, "
            f"password={bool(password_field.input_value())}",
        )

    def submit(self) -> None:
        _wait_for_network_idle(self.page)
        _click_first_visible(
            [
                self.page.get_by_role("button", name=re.compile("log in|login", re.I)),
                self.page.get_by_role("button", name=re.compile("sign in", re.I)),
            ],
            "login button",
        )

    def _login_error_message(self) -> Optional[str]:
        candidates = [
            self.page.get_by_text(
                re.compile(
                    r"Login failed!\s*Unable to verify your login credentials\.?",
                    re.I,
                )
            ),
            self.page.get_by_text(re.compile(r"\bLogin failed\b", re.I)),
            self.page.get_by_text(
                re.compile(r"Unable to verify your login credentials", re.I)
            ),
            self.page.locator(".alert.alert-danger"),
            self.page.locator(".alert-danger"),
        ]
        for locator in candidates:
            try:
                if locator.count() > 0 and locator.first.is_visible():
                    text = locator.first.text_content() or ""
                    text = re.sub(r"\s+", " ", text).strip()
                    return text or "Login failed"
            except PlaywrightTimeoutError:
                continue
        return None

    def _app_is_visible(self) -> bool:
        app_chrome = self.page.locator(
            "div.sidebar, ul.acc-menu, nav[role='navigation']"
        )
        login_form = self.page.locator(
            "input[type='password'], input[name*='password' i]"
        )
        try:
            if app_chrome.count() > 0 and app_chrome.first.is_visible():
                return True
            if login_form.count() == 0:
                return True
        except PlaywrightTimeoutError:
            return False
        return False

    def verify(self, timeout_ms: int = 15000) -> None:
        self.page.wait_for_timeout(500)
        start = time.monotonic()
        while True:
            if self._app_is_visible():
                return

            if (time.monotonic() - start) * 1000 >= timeout_ms:
                break
            self.page.wait_for_timeout(250)

        raise SystemExit(
            "Login did not complete within the expected time. If credentials are correct, the site may require extra steps (e.g., CAPTCHA/2FA) or the page UI changed."
        )


@dataclass(frozen=True)
class Config:
    helm_url: str
    email: str
    password: str
    headless: bool
    debug: bool

    @staticmethod
    def load(dotenv_path: Path = DOTENV_PATH) -> "Config":
        load_dotenv(dotenv_path=dotenv_path, override=True, encoding="utf-8-sig")

        return Config(
            helm_url=(
                "https://mybeautyandcareltd1.myhelm.app/login.php?type=standard"
            ).strip(),
            email=_require_env("HELM_EMAIL").strip(),
            password=_require_env("HELM_PASSWORD"),
            headless=_env_flag(
                "AUTOMATION_HEADLESS", default=_env_flag("HEADLESS", default=False)
            ),
            debug=_env_flag("DEBUG", default=False),
        )


def _flatten_json(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        column = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            flattened.update(_flatten_json(item, column))
        elif isinstance(item, list):
            flattened[column] = str(item)
        else:
            flattened[column] = item
    return flattened


def run(config: Config) -> None:
    _log_info(config.debug, f"Loaded .env from: {DOTENV_PATH}")
    _log_info(config.debug, f"HELM_URL: {config.helm_url}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config.headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            login = LoginFlow(page, config)
            login.open()
            login.fill_credentials()
            login.submit()
            page.wait_for_load_state("domcontentloaded")
            login.verify()
            _log_step("Step 1: Login to Helm")

            _click_pregen_failure(page)
            _log_step("Step 2: Click Pregen failure")

            _select_all_orders_on_page(page)
            _log_step("Step 3: Click select all on page checkbox")

            _open_bulk_action_dropdown(page)
            _log_step("Step 4: Click Select Bulk Action")

            _select_set_shipping_bulk_action(page)
            _log_step("Step 5: Select Set Shipping")

            time.sleep(2)
        finally:
            try:
                context.close()
            finally:
                browser.close()


if __name__ == "__main__":
    run(Config.load())
