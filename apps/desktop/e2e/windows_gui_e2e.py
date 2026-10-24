#!/usr/bin/env python3
"""Windows GUI end-to-end for the installed alphaloop desktop app.

Drives the NSIS (or MSI) install with tauri-driver and msedgedriver.
Market data stays offline when ALPHALOOP_OFFLINE_MARKET_DATA=1.
The passphrase vault is forced only when ALPHALOOP_SECRETS_BACKEND=passphrase.
Both flags default off in the product; this job sets them.

A step is PASS only after its assertion holds. A step that cannot run because
an earlier step failed is SKIPPED with that reason. This script never marks a
step passed because a later check was too hard.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable

CJK = re.compile(r"[\u3400-\u9fff]")
AUTH_TOKEN_RE = re.compile(r'("auth_token"\s*:\s*")[^"]*"')
TEST_SECRETS = ("alphaloop-e2e-keyring", "alphaloop-e2e-secret", "correct horse")
ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "e2e-artifacts"
SHOTS = ARTIFACTS / "screenshots"
LOGS = ARTIFACTS / "logs"

US_MESSAGES = (
    "美股股票 AAPL 的均值回归",
    "4 小时",
    "走样检验、样本外稳定",
    "至少 1 个标的、10 年、缺失不超过 5%",
)
CN_MESSAGES = (
    "A股股票 600519.SH 的均值回归",
    "4 小时",
    "走样检验、样本外稳定",
    "至少 1 个标的、10 年、缺失不超过 5%",
)


class StepResult:
    def __init__(self, name: str, status: str, screenshot: str, notes: str) -> None:
        self.name = name
        self.status = status
        self.screenshot = screenshot
        self.notes = notes


def prepare_env() -> tuple[Path, Path]:
    base = Path(os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or ".")
    data = Path(os.environ["ALPHALOOP_DATA_ROOT"]) if os.environ.get("ALPHALOOP_DATA_ROOT") else base / "alphaloop-e2e-data"
    runtime = (
        Path(os.environ["ALPHALOOP_RUNTIME_ROOT"])
        if os.environ.get("ALPHALOOP_RUNTIME_ROOT")
        else base / "alphaloop-e2e-runtime"
    )
    if data.exists():
        shutil.rmtree(data, ignore_errors=True)
    if runtime.exists():
        shutil.rmtree(runtime, ignore_errors=True)
    data.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ["ALPHALOOP_DATA_ROOT"] = str(data)
    os.environ["ALPHALOOP_RUNTIME_ROOT"] = str(runtime)
    os.environ.setdefault("ALPHALOOP_OFFLINE_MARKET_DATA", "1")
    os.environ.pop("ALPHALOOP_SECRETS_BACKEND", None)
    os.environ.setdefault("ALPHALOOP_MAX_TRIALS", "1")
    os.environ.setdefault("ALPHALOOP_E2E_HOLD_RUNNING_SEC", "45")
    os.environ.setdefault("ALPHALOOP_REVIEWER", "deterministic")
    return data, runtime


def process_running(image: str) -> bool:
    completed = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
    )
    return image.lower() in (completed.stdout or "").lower()


INSTALLED_EXE: Path | None = None


def kill_app() -> None:
    images = ["alphaloop-engine.exe"]
    if INSTALLED_EXE is not None:
        images.append(INSTALLED_EXE.name)
    for image in images:
        subprocess.run(["taskkill", "/F", "/T", "/IM", image], check=False, capture_output=True)


def wait_port(port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 1):
                return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(f"127.0.0.1:{port} did not open")


def _registry_install_hints() -> list[str]:
    script = r"""
$paths = @(
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
Get-ItemProperty $paths -ErrorAction SilentlyContinue | ForEach-Object {
  if ([string]$_.DisplayName -notmatch 'alphaloop') { return }
  if ($_.DisplayIcon) { Write-Output ([string]$_.DisplayIcon) }
  if ($_.InstallLocation) { Write-Output ([string]$_.InstallLocation) }
}
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
    )
    hints: list[str] = []
    for line in (completed.stdout or "").splitlines():
        text = line.strip().strip('"')
        if "," in text:
            text = text.split(",", 1)[0].strip().strip('"')
        if text:
            hints.append(text)
    return hints


def _exe_candidates() -> list[Path]:
    found: list[Path] = []

    def add(path: Path) -> None:
        if path.is_file() and path.suffix.lower() == ".exe" and "uninstall" not in path.name.lower():
            if path not in found:
                found.append(path)

    for hint in _registry_install_hints():
        path = Path(hint)
        if path.is_dir():
            for child in path.glob("*.exe"):
                add(child)
        else:
            add(path)
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    folders: list[Path] = []
    if local.is_dir():
        folders.extend(path for path in local.glob("alphaloop*") if path.is_dir())
        programs = local / "Programs"
        if programs.is_dir():
            folders.extend(path for path in programs.glob("alphaloop*") if path.is_dir())
    for folder in folders:
        for child in folder.glob("*.exe"):
            add(child)
    return found


def find_installed_exe() -> Path | None:
    candidates = _exe_candidates()
    if not candidates:
        return None
    return candidates[0]


def install_silent(installer: Path) -> Path:
    if installer.suffix.lower() == ".msi":
        completed = subprocess.run(
            ["msiexec", "/i", str(installer), "/qn", "/norestart"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode not in (0, 3010):
            raise RuntimeError(f"msiexec exited {completed.returncode}: {completed.stdout} {completed.stderr}")
    else:
        completed = subprocess.run([str(installer), "/S"], check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                f"NSIS installer exited {completed.returncode}: {completed.stdout} {completed.stderr}"
            )
    global INSTALLED_EXE
    deadline = time.time() + 120
    while time.time() < deadline:
        found = find_installed_exe()
        if found is not None:
            INSTALLED_EXE = found
            unblock_tree(found.parent)
            return found
        time.sleep(1)
    raise RuntimeError("installer finished but no alphaloop executable was found from the uninstall registry or LocalAppData")


def unblock_tree(root: Path) -> None:
    """Drop Mark-of-the-Web on the installed tree.

    A medium-integrity WebView2 host with a zone identifier stays on a blank
    document, and SmartScreen can hold the unsigned engine before handshake.
    """
    if os.name != "nt" or not root.exists():
        return
    env = os.environ.copy()
    env["ALPHALOOP_UNBLOCK_ROOT"] = str(root)
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-ChildItem -LiteralPath $env:ALPHALOOP_UNBLOCK_ROOT -Recurse -Force -File | Unblock-File",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Unblock-File failed for {root}: {completed.stderr}")


def uninstall_silent(exe: Path | None) -> None:
    candidates: list[Path] = []
    if exe is not None:
        candidates.append(exe.parent / "uninstall.exe")
        candidates.append(exe.with_name("Uninstall alphaloop.exe"))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if local.is_dir():
        for path in local.rglob("uninstall.exe"):
            if "alphaloop" in str(path).lower():
                candidates.append(path)
    uninstaller = next((path for path in candidates if path.is_file()), None)
    if uninstaller is None:
        raise RuntimeError("uninstaller was not found next to the installed app")
    completed = subprocess.run([str(uninstaller), "/S"], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"uninstaller exited {completed.returncode}: {completed.stderr}")
    deadline = time.time() + 90
    while time.time() < deadline:
        if find_installed_exe() is None:
            return
        time.sleep(1)
    raise RuntimeError("uninstaller returned but the installed executable is still present")


def log_has_traceback(data_root: Path) -> str | None:
    for name in ("engine.log", "desktop.log"):
        path = data_root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "Traceback (most recent call last)" in text or "panicked at" in text:
            return f"{name} contains a traceback or panic"
    return None


def redact_text(text: str, secrets: tuple[str, ...] = TEST_SECRETS) -> str:
    text = AUTH_TOKEN_RE.sub(r'\1[redacted]"', text)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def assert_no_secret_leaks(root: Path, secrets: tuple[str, ...] = TEST_SECRETS) -> None:
    leaked: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".png":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r'"auth_token"\s*:\s*"(?!\[redacted\])', text):
            leaked.append(f"{path.name} still has auth_token")
        for secret in secrets:
            if secret and secret in text:
                leaked.append(f"{path.name} still has a test secret")
                break
    if leaked:
        raise AssertionError("redaction failed: " + "; ".join(leaked))


def redact_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".png":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        redacted = redact_text(text)
        if redacted != text:
            path.write_text(redacted, encoding="utf-8")
    assert_no_secret_leaks(root)


def assert_no_console_window() -> str:
    """Fail when the installed app or engine owns a console window."""
    if os.name != "nt":
        raise AssertionError("console window check only runs on Windows")
    import csv
    import ctypes
    from ctypes import wintypes

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Csv -NoTypeInformation",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    rows = list(csv.DictReader(completed.stdout.splitlines()))
    names: dict[int, str] = {}
    children: dict[int, list[int]] = {}
    parents: dict[int, int] = {}
    for row in rows:
        pid = int(row["ProcessId"])
        parent = int(row["ParentProcessId"])
        names[pid] = row["Name"]
        parents[pid] = parent
        children.setdefault(parent, []).append(pid)
    roots = [
        pid
        for pid, name in names.items()
        if name.lower() in {"alphaloop-desktop.exe", "alphaloop-engine.exe"}
    ]
    if not roots:
        raise AssertionError("alphaloop-desktop.exe is not running")
    tree: set[int] = set()
    stack = list(roots)
    while stack:
        pid = stack.pop()
        if pid in tree:
            continue
        tree.add(pid)
        stack.extend(children.get(pid, []))
    for pid, name in names.items():
        if name.lower() == "conhost.exe" and parents.get(pid) in tree:
            tree.add(pid)

    user32 = ctypes.windll.user32
    offenders: list[str] = []

    def visit(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        owner = int(pid.value)
        if owner not in tree:
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        visible = bool(user32.IsWindowVisible(hwnd))
        proc = names.get(owner, "").lower()
        # msedgewebview2.exe owns a ConsoleWindowClass window only while
        # msedgedriver is attached. The de-elevated installer smoke starts the
        # same binary without that driver and must still fail a real console.
        shell = proc in {
            "alphaloop-desktop.exe",
            "alphaloop-engine.exe",
            "conhost.exe",
            "cmd.exe",
            "powershell.exe",
            "pwsh.exe",
            "windowsterminal.exe",
            "openconsole.exe",
        }
        if (class_name.value == "ConsoleWindowClass" and shell) or (proc == "conhost.exe" and visible):
            offenders.append(f"{proc} class={class_name.value} pid={owner} visible={visible}")
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit)
    user32.EnumWindows(callback, 0)
    if offenders:
        raise AssertionError("console window open: " + "; ".join(offenders))
    return "no console window"


def copy_logs(data_root: Path, driver_log: Path) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    for name in ("engine.log", "desktop.log"):
        source = data_root / name
        if source.is_file():
            shutil.copy2(source, LOGS / name)
    destination = LOGS / "tauri-driver.log"
    if driver_log.is_file() and driver_log.resolve() != destination.resolve():
        shutil.copy2(driver_log, destination)
    if (LOGS / "engine.log").is_file() and (LOGS / "desktop.log").is_file():
        return
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if not local.is_dir():
        return
    for name in ("engine.log", "desktop.log"):
        if (LOGS / name).is_file():
            continue
        for candidate in local.glob(f"alphaloop*/{name}"):
            shutil.copy2(candidate, LOGS / name)
            break


class Session:
    def __init__(self, app: Path, driver_log: Path) -> None:
        from selenium import webdriver
        from selenium.webdriver.common.options import ArgOptions

        self.webdriver = webdriver
        self.app = app
        self.driver_log = driver_log
        native = os.environ["MSEDGEDRIVER"]
        self.proc = subprocess.Popen(
            ["tauri-driver", "--native-driver", native],
            stdout=driver_log.open("a", encoding="utf-8", buffering=1),
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        try:
            wait_port(4444, 40)
        except Exception:
            self.stop_driver()
            raise
        self.driver = self._connect()

    def _connect(self):
        from selenium.webdriver.common.options import ArgOptions

        options = ArgOptions()
        options.set_capability("browserName", "wry")
        # Do not wait for window.onload. The release shell keeps font and
        # asset requests open, and msedgedriver otherwise blocks the first
        # DOM call for its 300s renderer timeout.
        options.set_capability("pageLoadStrategy", "none")
        options.set_capability("tauri:options", {"application": str(self.app)})
        from selenium.webdriver.remote.client_config import ClientConfig

        # A wedged WebView2 renderer must fail the step. The default client
        # wait is long enough to burn the whole job with no traceback.
        client = ClientConfig(remote_server_addr="http://127.0.0.1:4444", timeout=90)
        driver = self.webdriver.Remote(
            command_executor="http://127.0.0.1:4444",
            options=options,
            client_config=client,
        )
        driver.implicitly_wait(0)
        driver.set_page_load_timeout(15)
        driver.set_script_timeout(30)
        try:
            driver.set_window_rect(x=40, y=40, width=1280, height=800)
        except Exception:
            pass
        return driver

    def restart(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass
        kill_app()
        image = INSTALLED_EXE.name if INSTALLED_EXE is not None else "alphaloop-desktop.exe"
        deadline = time.time() + 20
        while time.time() < deadline:
            if not process_running(image) and not process_running("alphaloop-engine.exe"):
                break
            time.sleep(0.4)
        self.driver = self._connect()

    def stop_driver(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass
        self.stop_driver()


def wait_css(driver, css: str, timeout: float = 30):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))


def assert_run_disabled(driver, reason_needle: str) -> None:
    """Run must be disabled, look disabled, and say why before anyone confirms."""
    from selenium.webdriver.common.by import By

    button = driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]")
    if button.is_enabled():
        raise AssertionError("Run was enabled before the blocking choice was made")
    if button.get_attribute("data-run-blocked") not in {"market", "source", "family", "unlicensed", "resolution"}:
        raise AssertionError(f"Run is disabled without a block reason: {button.get_attribute('data-run-blocked')}")
    opacity = driver.execute_script("return getComputedStyle(arguments[0]).opacity", button)
    if float(opacity) >= 0.99:
        raise AssertionError(f"disabled Run still looks fully opaque ({opacity})")
    reason = driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-blocked-reason]").text
    if reason_needle not in reason:
        raise AssertionError(f"blocked Run reason {reason!r} did not contain {reason_needle!r}")


def accept_unlicensed_source(driver) -> None:
    """The confirm card keeps Run disabled until a price source is chosen and acknowledged."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    radios = driver.find_elements(By.CSS_SELECTOR, "[data-testid^=price-source-]")
    if radios:
        testid = radios[0].get_attribute("data-testid")
        click(driver, f"[data-testid={testid}]")
    else:
        choice = driver.find_elements(By.CSS_SELECTOR, "[data-testid=unlicensed-source-choice]")
        if choice and not choice[0].is_selected():
            click(driver, "[data-testid=unlicensed-source-choice]")
    ack = WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=unlicensed-ack]")
    )
    if not ack.is_selected():
        click(driver, "[data-testid=unlicensed-ack]")
    WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]").is_enabled()
    )


def click(driver, css: str, timeout: float = 20):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
    element.click()
    return element


def go(driver, route: str) -> None:
    driver.execute_script("window.location.hash = arguments[0];", route)


def shell_text(driver) -> str:
    return driver.execute_script(
        "return document.querySelector('[data-testid=night-shell]')?.innerText || ''"
    ) or ""


def assert_no_banner(driver, data_root: Path) -> None:
    text = shell_text(driver)
    for needle in ("Traceback (most recent call last)", "panicked at"):
        if needle in text:
            raise AssertionError(f"shell shows {needle}")
    from selenium.webdriver.common.by import By

    for css in (
        "[data-testid=mutation-error]",
        "[data-testid=route-error]",
        "[data-testid=sidecar-stopped]",
    ):
        found = driver.find_elements(By.CSS_SELECTOR, css)
        if found and found[0].is_displayed():
            raise AssertionError(f"{css}: {found[0].text}")
    problem = log_has_traceback(data_root)
    if problem:
        raise AssertionError(problem)


def describe_page(driver) -> str:
    try:
        handles = driver.window_handles
    except Exception as error:
        handles = [f"unavailable: {error}"]
    try:
        details = driver.execute_script(
            """
            const body = document.body;
            return JSON.stringify({
              url: location.href,
              ready: document.readyState,
              title: document.title,
              root: !!document.getElementById('root'),
              shell: !!document.querySelector('[data-testid=night-shell]'),
              text: (body && body.innerText || '').slice(0, 240)
            });
            """
        )
    except Exception as error:
        details = f"script failed: {error}"
    return f"handles={handles} page={details}"


def wait_engine(driver, timeout: float = 90) -> None:
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.by import By

    deadline = time.time() + timeout
    last_error = "night-shell did not report data-engine-phase=running"
    while time.time() < deadline:
        try:
            phase = driver.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute(
                "data-engine-phase"
            )
            if phase == "running":
                break
            last_error = f"data-engine-phase={phase}"
        except TimeoutException as error:
            last_error = f"renderer timeout: {error.msg if getattr(error, 'msg', None) else error}"
        except WebDriverException as error:
            last_error = str(error).splitlines()[0][:300]
        time.sleep(0.5)
    else:
        raise AssertionError(f"{last_error}; {describe_page(driver)}")
    deadline = time.time() + 30
    while time.time() < deadline:
        engine_up = process_running("alphaloop-engine.exe")
        app_up = INSTALLED_EXE is None or process_running(INSTALLED_EXE.name)
        if engine_up and app_up:
            return
        time.sleep(0.4)
    raise AssertionError("UI reports the engine running but the sidecar or installed executable is not in the process list")


def chrome_text(driver, css: str) -> str:
    return driver.execute_script(
        """
        const root = document.querySelector(arguments[0]);
        if (!root) return "";
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const parts = [];
        let node;
        while ((node = walker.nextNode())) {
          const parent = node.parentElement;
          if (parent && parent.closest("[data-user-content]")) continue;
          parts.push(node.nodeValue || "");
        }
        return parts.join("");
        """,
        css,
    ) or ""


def assert_no_cjk(driver, css: str, label: str) -> None:
    text = chrome_text(driver, css)
    if not text.strip():
        raise AssertionError(f"{label} had no text to check")
    found = "".join(CJK.findall(text))
    if found:
        raise AssertionError(f"{label} contains CJK {found[:24]!r} in: {text[:400]}")


def set_language(driver, value: str, rail_needle: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    click(driver, "[data-testid=rail-settings]")
    wait_css(driver, "[data-testid=settings-page]")
    click(driver, f"[data-testid=ui-language-option-{value}]")
    WebDriverWait(driver, 20).until(
        lambda d: rail_needle in d.find_element(By.CSS_SELECTOR, "[data-testid=rail]").text
    )


def set_input(driver, css: str, value: str) -> None:
    driver.execute_script(
        """
        const input = document.querySelector(arguments[0]);
        if (!input) throw new Error("missing " + arguments[0]);
        const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
        proto.set.call(input, arguments[1]);
        input.dispatchEvent(new Event("input", {bubbles: true}));
        """,
        css,
        value,
    )


def submit_dialogue(driver, message: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    wait_css(driver, "[data-testid=dialogue-input]", 40)

    def ready(d):
        if d.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-card]"):
            return True
        inputs = d.find_elements(By.CSS_SELECTOR, "[data-testid=dialogue-input]")
        if inputs and (inputs[0].get_attribute("value") or "") == "":
            return True
        errors = d.find_elements(By.CSS_SELECTOR, "[data-testid=mutation-error]")
        if errors and errors[0].is_displayed():
            raise AssertionError(f"dialogue error: {errors[0].text}")
        return False

    driver.execute_script(
        """
        const input = document.querySelector("[data-testid=dialogue-input]");
        if (!input) throw new Error("dialogue input missing");
        const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
        proto.set.call(input, arguments[0]);
        input.dispatchEvent(new Event("input", {bubbles: true}));
        if (!input.form) throw new Error("dialogue input has no form");
        input.form.requestSubmit();
        """,
        message,
    )
    WebDriverWait(driver, 45).until(ready)


def element_in_viewport(driver, css: str) -> bool:
    return bool(
        driver.execute_script(
            """
            const el = document.querySelector(arguments[0]);
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0 && rect.top >= -2 && rect.bottom <= window.innerHeight + 2;
            """,
            css,
        )
    )


def fit_confirm_card(driver) -> None:
    """Fit the whole confirm card at 100% zoom by growing the window, not by scaling."""
    driver.execute_script("document.documentElement.style.zoom = '1'")
    for _ in range(3):
        metrics = driver.execute_script(
            """
            const card = document.querySelector("[data-testid=confirm-run-card]");
            if (!card) return null;
            card.scrollIntoView({block: "start"});
            const rect = card.getBoundingClientRect();
            return {
              card: rect.height,
              bottom: rect.bottom,
              inner: window.innerHeight,
              zoom: document.documentElement.style.zoom || "1",
            };
            """
        )
        if not metrics:
            raise AssertionError("confirm card is missing")
        if metrics["zoom"] not in ("", "1", "1.0"):
            raise AssertionError(f"confirm card zoom is {metrics['zoom']}")
        if metrics["bottom"] <= metrics["inner"] + 2 and metrics["card"] > 0:
            break
        outer = driver.get_window_rect()
        chrome = max(80, int(outer["height"]) - int(metrics["inner"]))
        needed = int(metrics["bottom"]) + chrome + 32
        driver.set_window_rect(x=0, y=0, width=max(1440, int(outer["width"])), height=max(needed, 900))
    missing = [
        css
        for css in (
            "[data-testid=confirm-run-card] h1",
            "[data-testid=symbol-selection]",
            "[data-testid=confirm-run-start]",
        )
        if not element_in_viewport(driver, css)
    ]
    if missing:
        raise AssertionError("confirm card is still cropped; outside the viewport: " + ", ".join(missing))


def reset_page_zoom(driver) -> None:
    driver.execute_script("document.documentElement.style.zoom = '1'")
    try:
        driver.set_window_rect(x=40, y=40, width=1280, height=800)
    except Exception:
        pass


def create_until_confirm(driver, messages: tuple[str, ...]) -> str:
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    go(driver, "#/research")
    click(driver, "[data-testid=new-research-button]")
    wait_css(driver, "[data-testid=dialogue-input]", 40)
    for message in messages:
        if driver.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-card]"):
            break
        submit_dialogue(driver, message)
    WebDriverWait(driver, 40).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid=confirm-run-card]"))
    )
    href = driver.execute_script("return window.location.hash || ''") or ""
    research_id = href.rstrip("/").split("/")[-1]
    if not research_id or research_id == "research":
        raise AssertionError(f"confirm card did not open a research route: {href}")
    return research_id


def open_confirm_card(driver, research_id: str) -> None:
    go(driver, "#/research")
    click(
        driver,
        f"[data-testid=confirm-pinned-card][data-research-id='{research_id}'] a.list-open-confirm",
    )
    wait_css(driver, "[data-testid=confirm-run-card]", 30)
    href = driver.execute_script("return window.location.hash || ''") or ""
    if research_id not in href:
        raise AssertionError(f"card for {research_id} opened {href}")


def export_research_record(driver) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    primary = driver.find_elements(By.CSS_SELECTOR, "[data-testid=export-research-record-primary]")
    if primary and primary[0].is_displayed():
        primary[0].click()
    else:
        click(driver, "[data-testid=completed-tools-details] summary, details.completed-tools-details summary")
        click(driver, "[data-testid=export-research-record]")
    WebDriverWait(driver, 40).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid=export-success]"))
    )


def write_summary(results: list[StepResult]) -> None:
    lines = [
        "## Windows GUI end-to-end",
        "",
        "| Step | Result | Screenshot | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for item in results:
        notes = item.notes.replace("|", "/").replace("\n", " ")
        lines.append(f"| {item.name} | {item.status} | {item.screenshot or '—'} | {notes} |")
    lines.append("")
    text = "\n".join(lines)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "summary.md").write_text(text, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
    if len(sys.argv) != 2:
        print("usage: windows_gui_e2e.py <installer.exe>", file=sys.stderr)
        return 2
    installer = Path(sys.argv[1]).resolve()
    if not installer.is_file():
        print(f"installer not found: {installer}", file=sys.stderr)
        return 2
    if shutil.which("tauri-driver") is None:
        print("tauri-driver is not on PATH", file=sys.stderr)
        return 2
    native_driver = os.environ.get("MSEDGEDRIVER", "")
    if not native_driver or not Path(native_driver).is_file():
        print("MSEDGEDRIVER must be the msedgedriver.exe that matches the WebView2 Runtime", file=sys.stderr)
        return 2

    SHOTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    data_root, _runtime = prepare_env()
    driver_log = LOGS / "tauri-driver.log"
    driver_log.write_text(
        "tauri-driver --native-driver "
        f"{native_driver}\n"
        "msedgedriver stdout is discarded by tauri-driver; this file captures tauri-driver stderr.\n",
        encoding="utf-8",
    )
    results: list[StepResult] = []
    session: Session | None = None
    installed: Path | None = None
    blocked: str | None = None
    shot_index = 0
    seen_shots: dict[str, str] = {}
    step_shots: list[str] = []
    hash_log = LOGS / "screenshot-sha256.txt"
    hash_log.write_text("", encoding="utf-8")

    def note_shot(filename: str, digest: str) -> None:
        earlier = seen_shots.get(digest)
        if earlier is not None and earlier != filename:
            raise AssertionError(
                f"screenshot {filename} sha256 {digest} equals earlier shot {earlier}"
            )
        seen_shots[digest] = filename
        with hash_log.open("a", encoding="utf-8") as handle:
            handle.write(f"{digest}  {filename}\n")

    for existing in sorted(SHOTS.glob("*.png")):
        note_shot(existing.name, hashlib.sha256(existing.read_bytes()).hexdigest())

    def shoot(name: str, *, filename: str | None = None) -> str:
        nonlocal shot_index
        if filename is None:
            shot_index += 1
            filename = f"{shot_index:02d}-{name}.png"
        path = SHOTS / filename
        if session is None:
            return ""
        try:
            session.driver.save_screenshot(str(path))
        except Exception as error:
            (LOGS / f"{filename}.error.txt").write_text(redact_text(str(error)), encoding="utf-8")
            raise
        note_shot(filename, hashlib.sha256(path.read_bytes()).hexdigest())
        step_shots.append(filename)
        return filename

    def run_step(name: str, slug: str, action: Callable[[], str]) -> None:
        nonlocal blocked
        step_shots.clear()
        if blocked:
            results.append(StepResult(name, "SKIPPED", "", f"blocked by earlier failure: {blocked}"))
            write_summary(results)
            return
        try:
            notes = action()
        except Exception as error:
            filename = step_shots[-1] if step_shots else ""
            if session is not None and not step_shots:
                try:
                    filename = shoot(slug)
                except Exception as shot_error:
                    error = RuntimeError(f"{error}; screenshot failed: {shot_error}")
            detail = redact_text(f"{error}")
            (LOGS / f"{slug}.txt").write_text(redact_text(traceback.format_exc()), encoding="utf-8")
            if session is not None:
                try:
                    (LOGS / f"{slug}-shell.txt").write_text(redact_text(shell_text(session.driver)), encoding="utf-8")
                except Exception:
                    pass
            results.append(StepResult(name, "FAIL", filename, detail[:500]))
            blocked = name
        else:
            filename = step_shots[-1] if step_shots else ""
            if session is not None and not step_shots:
                try:
                    filename = shoot(slug)
                except Exception as shot_error:
                    notes = f"{notes}; screenshot failed: {shot_error}"
            if len(step_shots) > 1:
                notes = f"{notes}; shots {', '.join(step_shots)}"
            results.append(StepResult(name, "PASS", filename, redact_text(notes)))
        write_summary(results)

    def step_install() -> str:
        nonlocal installed
        installed = install_silent(installer)
        return f"installed at {installed}"

    def step_launch() -> str:
        nonlocal session
        assert installed is not None
        session = Session(installed, driver_log)
        wait_engine(session.driver)
        assert_no_banner(session.driver, data_root)
        if not (data_root / "engine.log").is_file():
            raise AssertionError("engine did not write engine.log")
        console = assert_no_console_window()
        shoot("launch")
        return f"engine process is running and the shell has no error banner; {console}"

    def step_language() -> str:
        assert session is not None
        set_language(session.driver, "zh", "研究")
        shoot("language-zh")
        set_language(session.driver, "en", "Research")
        assert_no_cjk(session.driver, "[data-testid=rail]", "rail")
        return "switched zh then en; rail chrome has no CJK; zh UI shot taken while Chinese was showing"

    def step_keyring() -> str:
        assert session is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        def vault(d):
            return d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]")

        click(session.driver, "[data-testid=secret-vault-open]")
        wait_css(session.driver, "[data-testid=secret-vault]")
        WebDriverWait(session.driver, 20).until(lambda d: vault(d).get_attribute("data-backend") == "keyring")
        if vault(session.driver).get_attribute("data-locked") != "false":
            raise AssertionError("Windows credential manager reported the vault locked")
        if session.driver.find_elements(By.CSS_SELECTOR, "[data-testid=secret-passphrase]"):
            raise AssertionError("credential-manager mode showed a passphrase field")
        set_input(session.driver, "[data-testid=secret-alias]", "ci-keyring")
        set_input(session.driver, "[data-testid=secret-value]", "alphaloop-e2e-keyring")
        click(session.driver, "[data-testid=secret-save]")
        WebDriverWait(session.driver, 20).until(lambda d: "Saved." in (vault(d).text or ""))
        shoot("secrets-keyring")
        click(session.driver, "[data-testid=secret-vault-close]")
        return "default credential-manager backend stored a secret and was not locked"

    def relaunch_passphrase() -> None:
        nonlocal session
        assert installed is not None
        if session is not None:
            session.close()
        kill_app()
        os.environ["ALPHALOOP_SECRETS_BACKEND"] = "passphrase"
        session = Session(installed, driver_log)
        wait_engine(session.driver)
        assert_no_banner(session.driver, data_root)

    def step_secrets_create() -> str:
        relaunch_passphrase()
        assert session is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        def vault(d):
            return d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]")

        click(session.driver, "[data-testid=secret-vault-open]")
        wait_css(session.driver, "[data-testid=secret-vault]")
        WebDriverWait(session.driver, 15).until(lambda d: vault(d).get_attribute("data-backend"))
        backend = vault(session.driver).get_attribute("data-backend") or ""
        locked = vault(session.driver).get_attribute("data-locked")
        if locked != "false":
            raise AssertionError(f"vault was locked before a passphrase file existed (backend={backend})")
        if backend == "needs_choice":
            click(session.driver, "[data-testid=secret-choose-passphrase]")
            WebDriverWait(session.driver, 15).until(lambda d: vault(d).get_attribute("data-backend") == "passphrase")
        elif backend != "passphrase":
            raise AssertionError(
                f"expected the passphrase test backend, got {backend!r}. "
                "ALPHALOOP_SECRETS_BACKEND=passphrase did not take effect."
            )
        if vault(session.driver).get_attribute("data-locked") != "false":
            raise AssertionError("choosing passphrase storage without a file reported locked")
        assert_no_cjk(session.driver, "[data-testid=secret-vault]", "secrets panel")
        set_input(session.driver, "[data-testid=secret-alias]", "vendor-demo")
        set_input(session.driver, "[data-testid=secret-value]", "alphaloop-e2e-secret")
        set_input(session.driver, "[data-testid=secret-passphrase]", "correct horse")
        shoot("secrets-create")
        click(session.driver, "[data-testid=secret-save]")
        WebDriverWait(session.driver, 20).until(
            lambda d: (data_root / "secret-vault.bin").is_file() and vault(d).get_attribute("data-locked") == "false"
        )
        click(session.driver, "[data-testid=secret-vault-close]")
        return "passphrase file created and the vault stayed unlocked"

    def step_secrets_unlock() -> str:
        assert session is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        session.restart()
        wait_engine(session.driver)
        assert_no_banner(session.driver, data_root)
        click(session.driver, "[data-testid=secret-vault-open]")
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]").get_attribute("data-locked")
            == "true"
        )
        shoot("secrets-unlock")
        set_input(session.driver, "[data-testid=secret-passphrase]", "correct horse")
        click(session.driver, "[data-testid=secret-unlock]")
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]").get_attribute("data-locked")
            == "false"
        )
        shoot("secrets-unlocked")
        click(session.driver, "[data-testid=secret-vault-close]")
        return "restart locked the passphrase file; unlock cleared it"

    research_ids: dict[str, str] = {}

    def step_two_confirms() -> str:
        assert session is not None
        research_ids["us"] = create_until_confirm(session.driver, US_MESSAGES)
        go(session.driver, "#/research")
        wait_css(session.driver, f"[data-testid=confirm-pinned-card][data-research-id='{research_ids['us']}']")
        research_ids["cn"] = create_until_confirm(session.driver, CN_MESSAGES)
        go(session.driver, "#/research")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(session.driver, 20).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-pinned-card]")) >= 2
        )
        shoot("confirms-both")
        if research_ids["us"] == research_ids["cn"]:
            raise AssertionError("both dialogues wrote the same research id")
        open_confirm_card(session.driver, research_ids["us"])
        WebDriverWait(session.driver, 20).until(
            lambda d: "AAPL" in d.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        )
        session.driver.execute_script(
            """
            const needle = arguments[0];
            const card = document.querySelector('[data-testid=confirm-run-card]');
            const hit = [...(card ? card.querySelectorAll('*') : [])].find((el) =>
              [...el.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && (node.textContent || '').includes(needle))
            );
            (hit || card)?.scrollIntoView({block: 'center'});
            """,
            "AAPL",
        )
        try:
            fit_confirm_card(session.driver)
            shoot("confirms-us")
        finally:
            reset_page_zoom(session.driver)
        us_text = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "AAPL" not in us_text:
            raise AssertionError(f"US confirm card did not mention AAPL: {us_text[:300]}")
        assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "US confirm card")
        open_confirm_card(session.driver, research_ids["cn"])
        WebDriverWait(session.driver, 20).until(
            lambda d: "600519" in d.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        )
        session.driver.execute_script(
            """
            const needle = arguments[0];
            const card = document.querySelector('[data-testid=confirm-run-card]');
            const hit = [...(card ? card.querySelectorAll('*') : [])].find((el) =>
              [...el.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && (node.textContent || '').includes(needle))
            );
            (hit || card)?.scrollIntoView({block: 'center'});
            """,
            "600519",
        )
        try:
            fit_confirm_card(session.driver)
            shoot("confirms-cn")
        finally:
            reset_page_zoom(session.driver)
        cn_text = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "600519" not in cn_text:
            raise AssertionError(f"A-share confirm card did not mention 600519: {cn_text[:300]}")
        assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "A-share confirm card")
        return f"US {research_ids['us']} and A-share {research_ids['cn']} each opened their own confirm card"

    def step_blocked_run_before_confirm() -> str:
        assert session is not None
        unnamed = create_until_confirm(
            session.driver,
            (
                "MACD 金叉 均值回归",
                "4 小时",
                "走样检验、样本外稳定",
                "至少 1 个标的、10 年、缺失不超过 5%",
            ),
        )
        from selenium.webdriver.common.by import By

        card = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "doesn't name a market" not in card and "没有写市场" not in card:
            raise AssertionError(f"unnamed-market card did not ask which market: {card[:400]}")
        assert_run_disabled(session.driver, "market" if "doesn't name a market" in card else "没有写市场")
        reason = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-blocked-reason]").text
        if "doesn't name a market" in card and "doesn't name a market" not in reason:
            raise AssertionError(f"market-ask feedback missing: {reason}")
        if "没有写市场" in card and "没有写市场" not in reason:
            raise AssertionError(f"market-ask feedback missing: {reason}")
        go(session.driver, "#/research")
        return f"unnamed research {unnamed} kept Run disabled until a market is chosen"

    def step_momentum_blocked() -> str:
        assert session is not None
        create_until_confirm(
            session.driver,
            (
                "美股动量策略",
                "4 小时",
                "走样检验、样本外稳定",
                "至少 1 个标的、10 年、缺失不超过 5%",
            ),
        )
        from selenium.webdriver.common.by import By

        card = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "Not supported yet" not in card and "暂不支持" not in card:
            raise AssertionError(f"momentum card did not say the family is unsupported: {card[:400]}")
        needle = "cannot run yet" if "Not supported yet" in card else "这一族还不能开跑"
        assert_run_disabled(session.driver, needle)
        button = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]")
        if button.get_attribute("data-run-blocked") != "family":
            raise AssertionError("momentum Run was not blocked as a family")
        assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "momentum confirm card")
        go(session.driver, "#/research")
        return "momentum card says it is unsupported and Run is disabled with the same reason"

    def step_english_reference() -> str:
        assert session is not None
        go(session.driver, "#/glossary")
        wait_css(session.driver, "[data-testid=glossary-page]")
        assert_no_cjk(session.driver, "[data-testid=glossary-page]", "glossary")
        go(session.driver, "#/methods")
        wait_css(session.driver, "[data-testid=method-definition-display]")
        assert_no_cjk(session.driver, ".methods-layout", "methods")
        return "English glossary and methods rendered with no CJK"

    def step_run_and_export() -> str:
        assert session is not None
        open_confirm_card(session.driver, research_ids["us"])
        assert_run_disabled(session.driver, "Not selected")
        accept_unlicensed_source(session.driver)
        click(session.driver, "[data-testid=confirm-run-start]")
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(session.driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute("data-view")
            == "running"
        )
        shoot("running")
        WebDriverWait(session.driver, 240).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid=completed-screen]"))
        )
        assert_no_banner(session.driver, data_root)
        assert_no_cjk(session.driver, "[data-testid=completed-screen]", "conclusion page")
        export_research_record(session.driver)
        wait_css(session.driver, "[data-testid=export-success]")
        session.driver.execute_script(
            "document.querySelector('[data-testid=export-success]')?.scrollIntoView({block:'center'})"
        )
        shoot("conclusion")
        exports = list((data_root / "exports").glob("*"))
        if not exports:
            raise AssertionError("export reported success but exports/ is empty")
        return f"conclusion rendered; wrote {exports[0].name}"

    def step_delete_running() -> str:
        assert session is not None
        open_confirm_card(session.driver, research_ids["cn"])
        accept_unlicensed_source(session.driver)
        click(session.driver, "[data-testid=confirm-run-start]")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(session.driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute("data-view")
            == "running"
        )
        rid = research_ids["cn"]
        go(session.driver, "#/research")
        running_row = WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR,
                f"[data-testid=research-row][data-research-id='{rid}'][data-status=running]",
            )
        )
        pill = running_row.find_element(By.CSS_SELECTOR, "[data-testid=list-status-pill]")
        if pill.text.strip() != "Running":
            raise AssertionError(f"running row status is {pill.text!r}, expected Running")
        if "+08:00" not in running_row.text:
            raise AssertionError(f"expected local offset +08:00 on the running row, saw {running_row.text}")
        session.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            running_row,
        )
        shoot("before-delete-running", filename="11a-before-delete-running.png")
        click(
            session.driver,
            f"[data-testid=research-row][data-research-id='{rid}'][data-status=running] [data-testid=delete-research]",
            timeout=15,
        )
        click(session.driver, "[data-testid=in-app-confirm-accept]")
        WebDriverWait(session.driver, 20).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, f"[data-research-id='{rid}']")
        )
        phase = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute(
            "data-engine-phase"
        )
        if phase != "running":
            raise AssertionError(f"engine phase after delete is {phase}")
        if not process_running("alphaloop-engine.exe"):
            raise AssertionError("alphaloop-engine.exe exited when a running research was deleted")
        assert_no_banner(session.driver, data_root)
        us_id = research_ids["us"]
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, f"[data-testid=research-row][data-research-id='{us_id}']")
        )
        session.driver.execute_script(
            """
            const row = document.querySelector(arguments[0]);
            row?.scrollIntoView({block: 'center'});
            """,
            f"[data-testid=research-row][data-research-id='{us_id}']",
        )
        shoot("delete-running")
        return "deleted the running A-share research; engine process stayed up"

    def step_persist() -> str:
        assert session is not None
        session.restart()
        wait_engine(session.driver)
        assert_no_banner(session.driver, data_root)
        go(session.driver, "#/research")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        us_id = research_ids["us"]
        cn_id = research_ids["cn"]
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, f"[data-research-id='{us_id}']")
        )
        if session.driver.find_elements(By.CSS_SELECTOR, f"[data-research-id='{cn_id}']"):
            raise AssertionError("deleted research reappeared after restart")
        click(session.driver, f"[data-testid=research-row][data-research-id='{us_id}'] a")
        wait_css(session.driver, "[data-testid=completed-screen]")
        shoot("persist")
        return "completed US research is still listed after restart"

    def step_uninstall() -> str:
        console = ""
        try:
            if session is not None:
                console = assert_no_console_window()
                click(session.driver, "[data-testid=rail-settings]")
                wait_css(session.driver, "[data-testid=about-card]")
                shoot("before-uninstall")
                try:
                    session.driver.quit()
                except Exception:
                    pass
        finally:
            kill_app()
            uninstall_silent(installed)
        note = "silent uninstall removed the installed executable"
        if console:
            note = f"{note}; {console}"
        return note

    try:
        run_step("install silently", "install", step_install)
        run_step("first launch, engine healthy, no traceback", "launch", step_launch)
        run_step("switch zh then en; English rail has no CJK", "language", step_language)
        run_step("secrets: Windows credential manager is not locked", "secrets-keyring", step_keyring)
        run_step("secrets: no file is not locked; create passphrase", "secrets-create", step_secrets_create)
        run_step("restart and unlock passphrase", "secrets-unlock", step_secrets_unlock)
        run_step("US and A-share confirm cards open their own research", "confirms", step_two_confirms)
        run_step("blocked Run stays disabled before confirm", "blocked-run", step_blocked_run_before_confirm)
        run_step("momentum card and Run agree the family cannot run", "momentum-blocked", step_momentum_blocked)
        run_step("English glossary and methods have no CJK", "en-reference", step_english_reference)
        run_step("run to conclusion and export a file", "conclusion", step_run_and_export)
        run_step("delete a running research; engine stays up", "delete-running", step_delete_running)
        run_step("close and reopen; data persists", "persist", step_persist)
    finally:
        # Uninstall is its own step and still runs when an earlier step failed.
        if installed is not None:
            previous = blocked
            blocked = None
            run_step("uninstall silently", "uninstall", step_uninstall)
            if previous and results[-1].status == "PASS":
                blocked = previous
        if session is not None:
            session.close()
        kill_app()
        copy_logs(data_root, driver_log)
        write_summary(results)
        redact_tree(ARTIFACTS)

    failed = [item for item in results if item.status == "FAIL"]
    print(redact_text((ARTIFACTS / "summary.md").read_text(encoding="utf-8")))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
