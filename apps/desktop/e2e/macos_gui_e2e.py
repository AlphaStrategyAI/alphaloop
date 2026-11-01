#!/usr/bin/env python3
"""macOS GUI end-to-end for the unpacked alphaloop.app.

Mirrors apps/desktop/e2e/windows_gui_e2e.py. Official tauri-driver cannot drive
WKWebView (safaridriver automates Safari only; see
https://v2.tauri.app/develop/tests/webdriver/). This script launches the
ad-hoc signed .app from alphaloop_*_macos_arm64.app.tar.gz with
ALPHALOOP_WEBDRIVER=1 and drives the embedded W3C server
(tauri-plugin-wdio-webdriver) with Selenium. A normal launch does not set that
variable, so the port stays closed. The DMG is not mounted: it wraps this
same .app, and the volume is read-only.

Gatekeeper still applies to a browser-downloaded, notarized-missing build.
CI strips com.apple.quarantine and execs the Mach-O directly, because `open`
goes through LaunchServices. Keychain ACL prompts are not skipped: the
keyring step has to store a secret or the job fails.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable

E2E_DIR = Path(__file__).resolve().parent
if str(E2E_DIR) not in sys.path:
    sys.path.insert(0, str(E2E_DIR))

_SPEC = importlib.util.spec_from_file_location("windows_gui_e2e", E2E_DIR / "windows_gui_e2e.py")
assert _SPEC and _SPEC.loader
win = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(win)

WEBDRIVER_PORT = int(os.environ.get("TAURI_WEBDRIVER_PORT") or "4445")
INSTALL_ROOT_NAME = "alphaloop-e2e-install"


def pids_from_ps(text: str, name: str, own_pid: int) -> list[int]:
    """Match the executable basename, not the 15-character Darwin comm field.

    `pgrep -x alphaloop-engine` misses the engine: the kernel comm is 15
    bytes plus a NUL, so the process shows up as alphaloop-engin.
    """
    found: list[int] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, sep, command = stripped.partition(" ")
        if not sep:
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid == own_pid:
            continue
        executable = command.strip().split(" ", 1)[0]
        if Path(executable).name == name:
            found.append(pid)
    return found


def _ps_text() -> str:
    completed = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout or ""


def pids_for_name(name: str) -> list[int]:
    return pids_from_ps(_ps_text(), name, os.getpid())


def process_running(image: str) -> bool:
    name = image[:-4] if image.lower().endswith(".exe") else image
    return bool(pids_for_name(name))


def kill_app() -> None:
    for name in ("alphaloop", "alphaloop-engine"):
        for pid in pids_for_name(name):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def wait_port(port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.4):
                return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(f"127.0.0.1:{port} did not open")


def wait_port_closed(port: int, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.3):
                time.sleep(0.2)
        except OSError:
            return
    raise TimeoutError(f"127.0.0.1:{port} stayed open after the app was killed")


def clear_quarantine(path: Path) -> None:
    subprocess.run(
        ["xattr", "-dr", "com.apple.quarantine", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )


def verify_signature(app: Path) -> None:
    """Confirm the ad-hoc signature. Untar sometimes drops it; sign again with `-`."""
    completed = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return
    resigned = subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app)],
        check=False,
        capture_output=True,
        text=True,
    )
    if resigned.returncode != 0:
        raise RuntimeError(f"ad-hoc re-sign failed for {app}: {resigned.stdout} {resigned.stderr}")
    checked = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)],
        check=False,
        capture_output=True,
        text=True,
    )
    if checked.returncode != 0:
        raise RuntimeError(
            f"codesign --verify failed for {app}: {completed.stdout} {completed.stderr} {checked.stderr}"
        )


def bundle_executable(app: Path) -> Path:
    plist = app / "Contents" / "Info.plist"
    completed = subprocess.run(
        ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleExecutable", str(plist)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"CFBundleExecutable missing: {completed.stderr}")
    binary = app / "Contents" / "MacOS" / completed.stdout.strip()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"bundle executable missing: {binary}")
    return binary


def install_product(source: Path) -> Path:
    """Unpack or copy the .app into a temp directory CI is allowed to delete."""
    base = Path(os.environ.get("RUNNER_TEMP") or "/tmp")
    dest_root = base / INSTALL_ROOT_NAME
    if dest_root.exists():
        import shutil

        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True)
    if source.is_dir() and source.name.endswith(".app"):
        subprocess.run(["ditto", str(source), str(dest_root / source.name)], check=True)
    elif source.is_file():
        clear_quarantine(source)
        subprocess.run(["tar", "-xzf", str(source), "-C", str(dest_root)], check=True)
    else:
        raise RuntimeError(f"installer not found: {source}")
    apps = [path for path in dest_root.iterdir() if path.suffix == ".app" and path.is_dir()]
    if len(apps) != 1:
        raise RuntimeError(f"expected one .app from {source}, found {apps}")
    app = apps[0]
    clear_quarantine(app)
    verify_signature(app)
    bundle_executable(app)
    return app


def remove_product(app: Path | None) -> None:
    if app is None:
        return
    if app.exists():
        import shutil

        shutil.rmtree(app)
    if app.exists():
        raise RuntimeError(f"unpacked app is still present: {app}")
    parent = app.parent
    if parent.name == INSTALL_ROOT_NAME and parent.exists():
        import shutil

        shutil.rmtree(parent, ignore_errors=True)


def commit_choice(driver, css: str) -> None:
    """Select a radio or checkbox in a way WKWebView's scripted click will not.

    The embedded driver calls element.click(). On this WebKit that click does
    not update a React controlled radio, so Run stays disabled. Set `checked`
    through the input prototype and dispatch the events React listens for.
    Buttons keep using the shared click helper; this is only for choices.
    """
    driver.execute_script(
        """
        const input = document.querySelector(arguments[0]);
        if (!input) throw new Error('missing ' + arguments[0]);
        input.scrollIntoView({block: 'center', inline: 'nearest'});
        // Click the label while unchecked. That is the user gesture, and it
        // turns a checkbox on. Setting checked first would make the label
        // click toggle a checkbox back off. The setter is only a fallback,
        // taken from the node's own prototype so a cross-realm
        // HTMLInputElement setter is not used.
        const label = input.parentElement && input.parentElement.tagName === 'LABEL'
          ? input.parentElement : null;
        if (!input.checked && label) label.click();
        if (!input.checked) {
          let setChecked = null;
          for (let proto = Object.getPrototypeOf(input); proto; proto = Object.getPrototypeOf(proto)) {
            const desc = Object.getOwnPropertyDescriptor(proto, 'checked');
            if (desc && desc.set) { setChecked = desc.set; break; }
          }
          if (!setChecked) throw new Error('no checked setter on ' + input.tagName);
          setChecked.call(input, true);
          const view = input.ownerDocument.defaultView || window;
          input.dispatchEvent(new view.MouseEvent('click', {bubbles: true}));
          input.dispatchEvent(new view.Event('input', {bubbles: true}));
          input.dispatchEvent(new view.Event('change', {bubbles: true}));
        }
        """,
        css,
    )


def accept_unlicensed_source(driver) -> None:
    from selenium.webdriver.support.ui import WebDriverWait

    # price-source-picker is a div and matches [data-testid^=price-source-].
    # Pick the input in the page, with a quoted attribute selector.
    picked = driver.execute_script(
        """
        const ids = ['price-source-yahoo_daily', 'price-source-akshare_sina_daily'];
        for (const id of ids) {
          const node = document.querySelector('[data-testid="' + id + '"]');
          if (node && node.tagName === 'INPUT') return id;
        }
        const choice = document.querySelector('[data-testid="unlicensed-source-choice"]');
        if (choice && choice.tagName === 'INPUT' && !choice.checked) return 'unlicensed-source-choice';
        const seen = [...document.querySelectorAll('[data-testid*="price-source"], [data-testid*="unlicensed"]')]
          .map((node) => node.tagName + ':' + node.getAttribute('data-testid'));
        return 'NONE ' + seen.join('|');
        """
    )
    if not isinstance(picked, str) or picked.startswith("NONE"):
        raise AssertionError(f"price source input was not found: {picked}")
    commit_choice(driver, f'[data-testid="{picked}"]')

    def ack_checked(current) -> bool | None:
        return current.execute_script(
            """
            const node = document.querySelector('[data-testid="unlicensed-ack"]');
            if (!node) return null;
            return !!node.checked;
            """
        )

    deadline = time.time() + 15
    state: bool | None = None
    while time.time() < deadline:
        state = ack_checked(driver)
        if state is not None:
            break
        time.sleep(0.25)
    if state is None:
        raise AssertionError("unlicensed acknowledgement checkbox did not appear")
    if state is not True:
        commit_choice(driver, '[data-testid="unlicensed-ack"]')
    WebDriverWait(driver, 15).until(
        lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]").is_enabled()
    )


def present_confirm_card(driver) -> str:
    """Grow the window the way Windows does.

    macos-15 guests have no VMware Tools, so the framebuffer stays about
    1024x768 and the window server will not grow the card onto one screen.
    Scrolling the symbol list into view keeps the screenshot honest.
    """
    try:
        win.fit_confirm_card(driver)
    except AssertionError as error:
        if "confirm card is still cropped" not in str(error):
            raise
        driver.execute_script(
            """
            const symbol = document.querySelector('[data-testid=symbol-selection]');
            const card = document.querySelector('[data-testid=confirm-run-card]');
            (symbol || card)?.scrollIntoView({block: 'center'});
            """
        )
        return "display cannot grow; scrolled the symbol list into view"
    return "confirm card fits one viewport"


def assert_no_controlling_terminal(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-o", "tty=", "-p", str(pid)],
        check=False,
        capture_output=True,
        text=True,
    )
    tty = (completed.stdout or "").strip()
    if tty not in {"??", "?", ""}:
        raise AssertionError(f"app is attached to a terminal ({tty})")
    return "no controlling terminal"


class Session:
    """Launch the .app ourselves and attach Selenium to its embedded server.

    tauri-driver's application capability starts msedgedriver or WebKitWebDriver.
    Neither attaches to a macOS WKWebView. The plugin listens only after
    ALPHALOOP_WEBDRIVER=1, on 127.0.0.1.
    """

    def __init__(self, app: Path, app_log: Path) -> None:
        from selenium import webdriver

        self.webdriver = webdriver
        self.app = app
        self.binary = bundle_executable(app)
        self.app_log = app_log
        self.proc: subprocess.Popen[str] | None = None
        self.driver = None
        self.launch()

    def launch(self) -> None:
        os.environ["ALPHALOOP_WEBDRIVER"] = "1"
        os.environ["TAURI_WEBDRIVER_PORT"] = str(WEBDRIVER_PORT)
        wait_port_closed(WEBDRIVER_PORT, timeout=5) if _port_open(WEBDRIVER_PORT) else None
        self.app_log.parent.mkdir(parents=True, exist_ok=True)
        handle = self.app_log.open("a", encoding="utf-8", buffering=1)
        handle.write(f"\n--- launch {self.binary} ALPHALOOP_WEBDRIVER=1 port {WEBDRIVER_PORT} ---\n")
        handle.flush()
        self.proc = subprocess.Popen(
            [str(self.binary)],
            cwd=str(self.binary.parent),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if self.proc.poll() is not None:
                    self._note_exit()
                try:
                    with socket.create_connection(("127.0.0.1", WEBDRIVER_PORT), 0.4):
                        break
                except OSError:
                    time.sleep(0.3)
            else:
                raise TimeoutError(f"127.0.0.1:{WEBDRIVER_PORT} did not open")
            self.driver = self._connect()
        except Exception:
            if self.proc is not None and self.proc.poll() is not None:
                try:
                    self._note_exit()
                except Exception:
                    self.stop_app()
                    raise
            self.stop_app()
            raise

    def _note_exit(self) -> None:
        if self.proc is not None and self.proc.poll() is not None:
            tail = ""
            if self.app_log.is_file():
                tail = self.app_log.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"alphaloop exited {self.proc.returncode} before WebDriver attached\n{tail}")

    def _connect(self):
        from selenium.webdriver.common.options import ArgOptions
        from selenium.webdriver.remote.client_config import ClientConfig

        options = ArgOptions()
        # The plugin accepts capabilities and ignores browserName. "wry" matches
        # the Windows tauri-driver session and is not Chrome-for-Testing.
        options.set_capability("browserName", "wry")
        options.set_capability("pageLoadStrategy", "none")
        client = ClientConfig(
            remote_server_addr=f"http://127.0.0.1:{WEBDRIVER_PORT}",
            timeout=90,
        )
        last: Exception | None = None
        deadline = time.time() + 60
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                self._note_exit()
            try:
                driver = self.webdriver.Remote(
                    command_executor=f"http://127.0.0.1:{WEBDRIVER_PORT}",
                    options=options,
                    client_config=client,
                )
                driver.implicitly_wait(0)
                try:
                    driver.set_page_load_timeout(15)
                except Exception:
                    pass
                try:
                    driver.set_script_timeout(30)
                except Exception:
                    pass
                try:
                    driver.set_window_rect(x=40, y=40, width=1280, height=800)
                except Exception:
                    pass
                return driver
            except Exception as error:
                last = error
                time.sleep(0.5)
        raise RuntimeError(f"WebDriver session did not start: {last}")

    def restart(self) -> None:
        self.close_driver()
        self.stop_app()
        deadline = time.time() + 20
        while time.time() < deadline:
            if not process_running("alphaloop") and not process_running("alphaloop-engine.exe"):
                break
            time.sleep(0.4)
        wait_port_closed(WEBDRIVER_PORT, timeout=20)
        self.launch()

    def close_driver(self) -> None:
        driver = self.driver
        self.driver = None
        if driver is None:
            return
        try:
            driver.quit()
        except Exception:
            pass

    def stop_app(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is not None and proc.poll() is None:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:
                pass
        kill_app()

    def close(self) -> None:
        self.close_driver()
        self.stop_app()


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), 0.3):
            return True
    except OSError:
        return False


def write_summary(results: list[win.StepResult]) -> None:
    lines = [
        "## macOS GUI end-to-end",
        "",
        "| Step | Result | Screenshot | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for item in results:
        notes = item.notes.replace("|", "/").replace("\n", " ")
        lines.append(f"| {item.name} | {item.status} | {item.screenshot or '—'} | {notes} |")
    lines.append("")
    text = "\n".join(lines)
    win.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (win.ARTIFACTS / "summary.md").write_text(text, encoding="utf-8")
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
        print("usage: macos_gui_e2e.py <alphaloop_*_macos_arm64.app.tar.gz>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1]).resolve()
    if not source.exists():
        print(f"installer not found: {source}", file=sys.stderr)
        return 2

    # wait_engine in the Windows module asks tasklist for alphaloop-engine.exe.
    # Point it at the Darwin process list before any step runs.
    win.process_running = process_running

    win.SHOTS.mkdir(parents=True, exist_ok=True)
    win.LOGS.mkdir(parents=True, exist_ok=True)
    data_root, _runtime = win.prepare_env()
    os.environ["ALPHALOOP_WEBDRIVER"] = "1"
    os.environ["TAURI_WEBDRIVER_PORT"] = str(WEBDRIVER_PORT)
    app_log = win.LOGS / "app-stdout.log"
    app_log.write_text(
        "macOS GUI e2e launches the .app binary directly. "
        "tauri-driver is not used: it has no WKWebView driver. "
        "ALPHALOOP_WEBDRIVER=1 starts tauri-plugin-wdio-webdriver on 127.0.0.1.\n",
        encoding="utf-8",
    )
    results: list[win.StepResult] = []
    session: Session | None = None
    installed: Path | None = None
    blocked: str | None = None
    shot_index = 0
    seen_shots: dict[str, str] = {}
    step_shots: list[str] = []
    hash_log = win.LOGS / "screenshot-sha256.txt"
    hash_log.write_text("", encoding="utf-8")

    def note_shot(filename: str, digest: str) -> None:
        earlier = seen_shots.get(digest)
        if earlier is not None and earlier != filename:
            raise AssertionError(f"screenshot {filename} sha256 {digest} equals earlier shot {earlier}")
        seen_shots[digest] = filename
        with hash_log.open("a", encoding="utf-8") as handle:
            handle.write(f"{digest}  {filename}\n")

    for existing in sorted(win.SHOTS.glob("*.png")):
        note_shot(existing.name, hashlib.sha256(existing.read_bytes()).hexdigest())

    def shoot(name: str, *, filename: str | None = None) -> str:
        nonlocal shot_index
        if filename is None:
            shot_index += 1
            filename = f"{shot_index:02d}-{name}.png"
        path = win.SHOTS / filename
        if session is None or session.driver is None:
            return ""
        try:
            session.driver.save_screenshot(str(path))
        except Exception as error:
            (win.LOGS / f"{filename}.error.txt").write_text(win.redact_text(str(error)), encoding="utf-8")
            raise
        note_shot(filename, hashlib.sha256(path.read_bytes()).hexdigest())
        step_shots.append(filename)
        return filename

    def run_step(name: str, slug: str, action: Callable[[], str]) -> None:
        nonlocal blocked
        step_shots.clear()
        if blocked:
            results.append(win.StepResult(name, "SKIPPED", "", f"blocked by earlier failure: {blocked}"))
            write_summary(results)
            return
        try:
            notes = action()
        except Exception as error:
            filename = step_shots[-1] if step_shots else ""
            if session is not None and session.driver is not None and not step_shots:
                try:
                    filename = shoot(slug)
                except Exception as shot_error:
                    error = RuntimeError(f"{error}; screenshot failed: {shot_error}")
            detail = win.redact_text(f"{error}")
            (win.LOGS / f"{slug}.txt").write_text(win.redact_text(traceback.format_exc()), encoding="utf-8")
            if session is not None and session.driver is not None:
                try:
                    (win.LOGS / f"{slug}-shell.txt").write_text(
                        win.redact_text(win.shell_text(session.driver)),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
            results.append(win.StepResult(name, "FAIL", filename, detail[:500]))
            blocked = name
        else:
            filename = step_shots[-1] if step_shots else ""
            if session is not None and session.driver is not None and not step_shots:
                try:
                    filename = shoot(slug)
                except Exception as shot_error:
                    notes = f"{notes}; screenshot failed: {shot_error}"
            if len(step_shots) > 1:
                notes = f"{notes}; shots {', '.join(step_shots)}"
            results.append(win.StepResult(name, "PASS", filename, win.redact_text(notes)))
        write_summary(results)

    def step_install() -> str:
        nonlocal installed
        installed = install_product(source)
        binary = bundle_executable(installed)
        win.INSTALLED_EXE = binary
        return f"unpacked at {installed}; binary {binary.name}"

    def step_launch() -> str:
        nonlocal session
        assert installed is not None
        kill_app()
        session = Session(installed, app_log)
        assert session.proc is not None
        win.wait_engine(session.driver)
        win.assert_no_banner(session.driver, data_root)
        if not (data_root / "engine.log").is_file():
            raise AssertionError("engine did not write engine.log")
        console = assert_no_controlling_terminal(session.proc.pid)
        shoot("launch")
        return f"engine process is running and the shell has no error banner; {console}"

    def step_language() -> str:
        assert session is not None and session.driver is not None
        win.set_language(session.driver, "zh", "研究")
        shoot("language-zh")
        win.set_language(session.driver, "en", "Research")
        win.assert_no_cjk(session.driver, "[data-testid=rail]", "rail")
        return "switched zh then en; rail chrome has no CJK; zh UI shot taken while Chinese was showing"

    def step_keyring() -> str:
        assert session is not None and session.driver is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        def vault(d):
            return d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]")

        win.click(session.driver, "[data-testid=secret-vault-open]")
        win.wait_css(session.driver, "[data-testid=secret-vault]")
        WebDriverWait(session.driver, 20).until(lambda d: vault(d).get_attribute("data-backend") == "keyring")
        if vault(session.driver).get_attribute("data-locked") != "false":
            raise AssertionError("macOS keychain reported the vault locked")
        if session.driver.find_elements(By.CSS_SELECTOR, "[data-testid=secret-passphrase]"):
            raise AssertionError("keychain mode showed a passphrase field")
        win.set_input(session.driver, "[data-testid=secret-alias]", "ci-keyring")
        win.set_input(session.driver, "[data-testid=secret-value]", "alphaloop-e2e-keyring")
        win.click(session.driver, "[data-testid=secret-save]")
        WebDriverWait(session.driver, 20).until(lambda d: "Saved." in (vault(d).text or ""))
        shoot("secrets-keyring")
        win.click(session.driver, "[data-testid=secret-vault-close]")
        return "default keychain backend stored a secret and was not locked"

    def relaunch_passphrase() -> None:
        nonlocal session
        assert installed is not None
        os.environ["ALPHALOOP_SECRETS_BACKEND"] = "passphrase"
        if session is None:
            session = Session(installed, app_log)
        else:
            session.restart()
        assert session.driver is not None
        win.wait_engine(session.driver)
        win.assert_no_banner(session.driver, data_root)

    def step_secrets_create() -> str:
        relaunch_passphrase()
        assert session is not None and session.driver is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        def vault(d):
            return d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]")

        win.click(session.driver, "[data-testid=secret-vault-open]")
        win.wait_css(session.driver, "[data-testid=secret-vault]")
        WebDriverWait(session.driver, 15).until(lambda d: vault(d).get_attribute("data-backend"))
        backend = vault(session.driver).get_attribute("data-backend") or ""
        locked = vault(session.driver).get_attribute("data-locked")
        if locked != "false":
            raise AssertionError(f"vault was locked before a passphrase file existed (backend={backend})")
        if backend == "needs_choice":
            win.click(session.driver, "[data-testid=secret-choose-passphrase]")
            WebDriverWait(session.driver, 15).until(lambda d: vault(d).get_attribute("data-backend") == "passphrase")
        elif backend != "passphrase":
            raise AssertionError(
                f"expected the passphrase test backend, got {backend!r}. "
                "ALPHALOOP_SECRETS_BACKEND=passphrase did not take effect."
            )
        if vault(session.driver).get_attribute("data-locked") != "false":
            raise AssertionError("choosing passphrase storage without a file reported locked")
        win.assert_no_cjk(session.driver, "[data-testid=secret-vault]", "secrets panel")
        win.set_input(session.driver, "[data-testid=secret-alias]", "vendor-demo")
        win.set_input(session.driver, "[data-testid=secret-value]", "alphaloop-e2e-secret")
        win.set_input(session.driver, "[data-testid=secret-passphrase]", "correct horse")
        shoot("secrets-create")
        win.click(session.driver, "[data-testid=secret-save]")
        WebDriverWait(session.driver, 20).until(
            lambda d: (data_root / "secret-vault.bin").is_file() and vault(d).get_attribute("data-locked") == "false"
        )
        win.click(session.driver, "[data-testid=secret-vault-close]")
        return "passphrase file created and the vault stayed unlocked"

    def step_secrets_unlock() -> str:
        assert session is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        session.restart()
        assert session.driver is not None
        win.wait_engine(session.driver)
        win.assert_no_banner(session.driver, data_root)
        win.click(session.driver, "[data-testid=secret-vault-open]")
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]").get_attribute("data-locked")
            == "true"
        )
        shoot("secrets-unlock")
        win.set_input(session.driver, "[data-testid=secret-passphrase]", "correct horse")
        win.click(session.driver, "[data-testid=secret-unlock]")
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=secret-vault]").get_attribute("data-locked")
            == "false"
        )
        shoot("secrets-unlocked")
        win.click(session.driver, "[data-testid=secret-vault-close]")
        return "restart locked the passphrase file; unlock cleared it"

    research_ids: dict[str, str] = {}

    def step_two_confirms() -> str:
        assert session is not None and session.driver is not None
        research_ids["us"] = win.create_until_confirm(session.driver, win.US_MESSAGES)
        win.go(session.driver, "#/research")
        win.wait_css(session.driver, f"[data-testid=confirm-pinned-card][data-research-id='{research_ids['us']}']")
        research_ids["cn"] = win.create_until_confirm(session.driver, win.CN_MESSAGES)
        win.go(session.driver, "#/research")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(session.driver, 20).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-pinned-card]")) >= 2
        )
        shoot("confirms-both")
        if research_ids["us"] == research_ids["cn"]:
            raise AssertionError("both dialogues wrote the same research id")
        win.open_confirm_card(session.driver, research_ids["us"])
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
            us_fit = present_confirm_card(session.driver)
            shoot("confirms-us")
        finally:
            win.reset_page_zoom(session.driver)
        us_text = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "AAPL" not in us_text:
            raise AssertionError(f"US confirm card did not mention AAPL: {us_text[:300]}")
        win.assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "US confirm card")
        win.open_confirm_card(session.driver, research_ids["cn"])
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
            cn_fit = present_confirm_card(session.driver)
            shoot("confirms-cn")
        finally:
            win.reset_page_zoom(session.driver)
        cn_text = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-card]").text
        if "600519" not in cn_text:
            raise AssertionError(f"A-share confirm card did not mention 600519: {cn_text[:300]}")
        win.assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "A-share confirm card")
        return (
            f"US {research_ids['us']} and A-share {research_ids['cn']} each opened their own confirm card; "
            f"{us_fit}; {cn_fit}"
        )

    def step_blocked_run_before_confirm() -> str:
        assert session is not None and session.driver is not None
        unnamed = win.create_until_confirm(
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
        win.assert_run_disabled(session.driver, "market" if "doesn't name a market" in card else "没有写市场")
        reason = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-blocked-reason]").text
        if "doesn't name a market" in card and "doesn't name a market" not in reason:
            raise AssertionError(f"market-ask feedback missing: {reason}")
        if "没有写市场" in card and "没有写市场" not in reason:
            raise AssertionError(f"market-ask feedback missing: {reason}")
        win.go(session.driver, "#/research")
        return f"unnamed research {unnamed} kept Run disabled until a market is chosen"

    def step_momentum_blocked() -> str:
        assert session is not None and session.driver is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        win.go(session.driver, "#/research")
        win.click(session.driver, "[data-testid=new-research-button]")
        win.wait_css(session.driver, "[data-testid=dialogue-input]", 40)
        win.submit_dialogue(session.driver, "美股动量策略")

        def blocked_intake(driver):
            if driver.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-card]"):
                return False
            text = driver.find_element(By.CSS_SELECTOR, ".draft-layout").text
            return "Not supported yet" in text or "暂不支持" in text

        WebDriverWait(session.driver, 30).until(blocked_intake)
        body = session.driver.find_element(By.CSS_SELECTOR, ".draft-layout").text
        for banned in (
            "How much effective research time",
            "最多允许多少有效研究时间",
            "要按均值回归继续",
            "Continue with mean reversion",
            "Continue as mean reversion",
        ):
            if banned in body:
                raise AssertionError(f"momentum intake continued: {banned}")
        if session.driver.find_elements(By.CSS_SELECTOR, "[data-testid=mean-reversion-continue]"):
            raise AssertionError("momentum offered continue as mean reversion")
        if session.driver.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-start]"):
            raise AssertionError("momentum thesis opened Run")
        chips = session.driver.find_elements(By.CSS_SELECTOR, "[data-family-id]")
        chip_ids = [item.get_attribute("data-family-id") for item in chips]
        if chip_ids != [
            "low_volatility",
            "stock_bond_rebalance",
            "mean_reversion",
            "fundamental_factor",
            "all_weather",
        ]:
            raise AssertionError(f"momentum chips {chip_ids}")
        for item in chips:
            if item.get_attribute("aria-pressed") != "false":
                raise AssertionError("a family chip was preselected")
        win.click(session.driver, "[data-testid=family-chip-mean_reversion]")
        WebDriverWait(session.driver, 30).until(
            lambda d: "Switched to mean reversion." in d.find_element(By.CSS_SELECTOR, ".draft-layout").text
            or "已改用均值回归" in d.find_element(By.CSS_SELECTOR, ".draft-layout").text
        )
        for message in (
            "4 小时",
            "走样检验、样本外稳定",
            "至少 1 个标的、10 年、缺失不超过 5%",
        ):
            if session.driver.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-card]"):
                break
            win.submit_dialogue(session.driver, message)
        WebDriverWait(session.driver, 40).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "[data-testid=confirm-run-card]")
        )
        after = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]")
        if after.get_attribute("data-run-blocked") == "family":
            raise AssertionError("mean-reversion chip left Run blocked as a family")
        win.assert_no_cjk(session.driver, "[data-testid=confirm-run-card]", "momentum confirm card")
        win.go(session.driver, "#/research")
        return "momentum intake is blocked, then a mean-reversion chip re-pick can reach confirm"

    def step_english_reference() -> str:
        assert session is not None and session.driver is not None
        win.go(session.driver, "#/glossary")
        win.wait_css(session.driver, "[data-testid=glossary-page]")
        win.assert_no_cjk(session.driver, "[data-testid=glossary-page]", "glossary")
        win.go(session.driver, "#/methods")
        win.wait_css(session.driver, "[data-testid=method-definition-display]")
        win.assert_no_cjk(session.driver, ".methods-layout", "methods")
        return "English glossary and methods rendered with no CJK"

    def step_en_time_examples() -> str:
        assert session is not None and session.driver is not None
        driver = session.driver
        from selenium.webdriver.support.ui import WebDriverWait

        shown: list[str] = []
        for answer, label in (("30 minutes", "30 min"), ("12 hours", "12 h")):
            win.start_new_research(driver)
            win.submit_accepted(driver, win.EN_THESIS, win.HOURS_PROMPT)
            win.submit_accepted(driver, answer, win.METHODS_PROMPT)
            WebDriverWait(driver, 15).until(lambda d, expected=label: expected in win.slot_text(d, "max_effective_hours"))
            win.assert_slot_filled(driver, "max_effective_hours", label)
            methods = win.slot_text(driver, "round1_methods")
            if "Not locked" not in methods:
                raise AssertionError(f"{answer!r} also filled methods: {methods!r}")
            shown.append(f"{answer} → {label}")
        driver.execute_script(
            "document.querySelector('[data-testid=brief-slot-max_effective_hours]')"
            "?.scrollIntoView({block:'center'})"
        )
        shoot("en-time-examples")
        return "English time examples parsed and opened the methods prompt: " + "; ".join(shown)

    def step_en_methods_coverage() -> str:
        assert session is not None and session.driver is not None
        driver = session.driver
        win.start_new_research(driver)
        win.submit_accepted(driver, win.EN_THESIS, win.HOURS_PROMPT)
        win.submit_accepted(driver, "12 hours", win.METHODS_PROMPT)
        win.assert_slot_filled(driver, "max_effective_hours", "12 h")
        win.submit_accepted(driver, win.EN_METHODS, win.COVERAGE_PROMPT)
        methods = win.slot_text(driver, "round1_methods")
        for name in (
            "Subperiod robustness check",
            "Out-of-sample stability",
            "Concentration",
            "Turnover cost",
        ):
            if name not in methods:
                raise AssertionError(f"methods slot {methods!r} did not contain {name!r}")
        win.submit_accepted(driver, win.EN_COVERAGE, win.SLOTS_READY)
        win.wait_css(driver, "[data-testid=confirm-run-card]", 40)
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(driver, 20).until(lambda d: "At least 25 names" in win.slot_text(d, "coverage_floor"))
        coverage = win.slot_text(driver, "coverage_floor")
        for part in ("10 years", "missing no more than 5%"):
            if part not in coverage:
                raise AssertionError(f"coverage slot {coverage!r} did not contain {part!r}")
        win.assert_no_apology(win.conversation_text(driver))
        research_ids["en-slots"] = win.current_research_id(driver)
        driver.execute_script(
            "document.querySelector('[data-testid=brief-slot-coverage_floor]')"
            "?.scrollIntoView({block:'center'})"
        )
        shoot("en-methods-coverage")
        return (
            f"English methods and coverage examples parsed for {research_ids['en-slots']}; "
            "coverage floor is 25 names on a one-name list"
        )

    def step_no_source_n3() -> str:
        assert session is not None and session.driver is not None
        driver = session.driver
        research_id = research_ids["en-slots"]
        win.open_confirm_card(driver, research_id)
        win.assert_n3_blocks_run(driver, win.N3_EN, "Not selected", win.COVERAGE_FLOOR_EN)
        try:
            win.set_language(driver, "zh", "研究")
            win.open_confirm_card(driver, research_id)
            win.assert_n3_blocks_run(driver, win.N3_ZH, "待选择", win.COVERAGE_FLOOR_ZH)
            driver.execute_script(
                "document.querySelector('[data-testid=confirm-run-blocked-reason]')"
                "?.scrollIntoView({block:'center'})"
            )
            shoot("no-source-n3")
        finally:
            win.set_language(driver, "en", "Research")
        win.go(driver, "#/research")
        return (
            f"research {research_id} kept Run disabled with the N3 sentence in English and Chinese "
            "while the named list was also under the coverage floor"
        )

    def step_llm_settings() -> str:
        assert session is not None and session.driver is not None
        driver = session.driver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        def panel_text() -> str:
            return driver.find_element(By.CSS_SELECTOR, "[data-testid=settings-llm]").text

        win.go(driver, "#/settings/llm")
        win.wait_css(driver, "[data-testid=settings-llm]")
        if "not ready" in panel_text().lower():
            raise AssertionError(f"LLM page is still a placeholder: {panel_text()[:300]}")
        for testid in ("llm-base-url", "llm-api-key", "llm-model", "llm-local-status", "llm-save"):
            win.wait_css(driver, f"[data-testid={testid}]")
        key_input = driver.find_element(By.CSS_SELECTOR, "[data-testid=llm-api-key]")
        if key_input.get_attribute("type") != "password":
            raise AssertionError("API key field is not a password input")
        win.set_input(driver, "[data-testid=llm-base-url]", win.LLM_LOOPBACK_URL)

        def local_copy(current) -> bool:
            status = current.find_element(By.CSS_SELECTOR, "[data-testid=llm-local-status]").text
            no_key = current.find_elements(By.CSS_SELECTOR, "[data-testid=llm-no-key]")
            return "Using a local model" in status and bool(no_key) and "does not use an API key" in no_key[0].text

        def remote_copy(current) -> bool:
            status = current.find_element(By.CSS_SELECTOR, "[data-testid=llm-local-status]").text
            return "goes to this host" in status and not current.find_elements(By.CSS_SELECTOR, "[data-testid=llm-no-key]")

        WebDriverWait(driver, 15).until(local_copy)
        win.set_input(driver, "[data-testid=llm-base-url]", win.LLM_REMOTE_URL)
        WebDriverWait(driver, 15).until(remote_copy)
        win.set_input(driver, "[data-testid=llm-model]", win.LLM_MODEL)
        win.set_input(driver, "[data-testid=llm-api-key]", win.LLM_API_KEY)
        win.click(driver, "[data-testid=llm-privacy]")
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=llm-privacy]").is_selected()
        )
        win.click(driver, "[data-testid=llm-save]")
        WebDriverWait(driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "[data-testid=llm-saved]")
            and d.find_elements(By.CSS_SELECTOR, "[data-testid=llm-key-stored]")
        )
        if driver.find_element(By.CSS_SELECTOR, "[data-testid=llm-api-key]").get_attribute("value"):
            raise AssertionError("API key stayed in the form after save")
        settings = win._wait_llm_settings(data_root)
        if settings.get("llmBaseUrl") != win.LLM_REMOTE_URL or settings.get("llmModel") != win.LLM_MODEL:
            raise AssertionError(
                f"settings.json endpoint was {settings.get('llmBaseUrl')!r} / {settings.get('llmModel')!r}"
            )
        if settings.get("llmPrivacyAcknowledged") is not True:
            raise AssertionError("settings.json did not record the privacy acknowledgement")
        raw = json.dumps(settings)
        if win.LLM_API_KEY in raw:
            raise AssertionError("settings.json contains the API key")
        for banned in ("llmApiKey", "apiKey", "api_key", "ALPHALOOP_LLM_API_KEY"):
            if banned in settings:
                raise AssertionError(f"settings.json kept a secret field {banned}")
        vault = data_root / "secret-vault.bin"
        if not vault.is_file():
            raise AssertionError("passphrase vault file is missing after saving the API key")
        if win.LLM_API_KEY.encode() in vault.read_bytes():
            raise AssertionError("API key was written in cleartext to the vault file")
        win.go(driver, "#/settings/general")
        win.wait_css(driver, "[data-testid=about-card]")
        win.go(driver, "#/settings/llm")
        win.wait_css(driver, "[data-testid=llm-key-stored]", 20)
        driver.execute_script(
            "document.querySelector('[data-testid=settings-llm]')?.scrollIntoView({block:'center'})"
        )
        shoot("llm-settings")
        try:
            win.set_language(driver, "zh", "研究")
            win.click(driver, "[data-testid=settings-tab-llm]")
            win.wait_css(driver, "[data-testid=settings-llm]")
            zh = panel_text()
            for label in ("接入地址", "API 密钥", "模型名", "本机模型"):
                if label not in zh:
                    raise AssertionError(f"Chinese LLM page missing {label}: {zh[:300]}")
            if "not ready" in zh.lower() or "还没准备" in zh:
                raise AssertionError(f"Chinese LLM page is still a placeholder: {zh[:300]}")
            if not driver.find_elements(By.CSS_SELECTOR, "[data-testid=llm-key-stored]"):
                raise AssertionError("Chinese LLM page lost the stored-key line")
            status = driver.find_element(By.CSS_SELECTOR, "[data-testid=llm-local-status]").text
            if "内容会发到这个主机" not in status:
                raise AssertionError(f"Chinese remote-provider copy missing: {status}")
        finally:
            win.set_language(driver, "en", "Research")
        return "LLM form saved a remote endpoint; the API key is in the vault, not settings.json"

    def step_disclosed_family_buttons() -> str:
        assert session is not None and session.driver is not None
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        messages = (
            "美股低波策略",
            "4 小时",
            "走样检验、样本外稳定",
            "至少 1 个标的、10 年、缺失不超过 5%",
        )
        win.create_until_confirm(session.driver, messages)
        win.wait_css(session.driver, "[data-testid=dialogue-input]")
        win.wait_css(session.driver, "[data-testid=mean-reversion-continue]")
        cont = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=mean-reversion-continue]")
        decline = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=mean-reversion-decline]")
        if cont.text.strip() != "Continue with mean reversion" or decline.text.strip() != "Don't continue":
            raise AssertionError(f"answer buttons {cont.text!r} / {decline.text!r}")
        if cont.get_attribute("aria-pressed") != "false" or decline.get_attribute("aria-pressed") != "false":
            raise AssertionError("mean-reversion answers were preselected")
        win.assert_run_disabled(
            session.driver,
            "Confirm whether to continue with mean reversion before running.",
        )
        win.click(session.driver, "[data-testid=mean-reversion-decline]")
        WebDriverWait(session.driver, 30).until(
            lambda d: "OK, it won't run as mean reversion."
            in d.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").text
        )
        chips = session.driver.find_elements(By.CSS_SELECTOR, "[data-family-id]")
        chip_ids = [item.get_attribute("data-family-id") for item in chips]
        if chip_ids != [
            "low_volatility",
            "stock_bond_rebalance",
            "mean_reversion",
            "fundamental_factor",
            "all_weather",
        ]:
            raise AssertionError(f"chips after decline {chip_ids}")
        if session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-run-start]").is_enabled():
            raise AssertionError("Run enabled after declining mean reversion")
        win.go(session.driver, "#/research")
        win.create_until_confirm(session.driver, messages)
        win.click(session.driver, "[data-testid=mean-reversion-continue]")
        WebDriverWait(session.driver, 30).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, "[data-testid=mean-reversion-continue]")
        )
        win.assert_run_disabled(
            session.driver,
            "No data source selected yet. Pick one on the confirmation card before running.",
        )
        win.go(session.driver, "#/research")
        return "Don't continue keeps the draft and opens chips; Continue with mean reversion clears that gate"

    def step_run_and_export() -> str:
        assert session is not None and session.driver is not None
        win.open_confirm_card(session.driver, research_ids["us"])
        from selenium.webdriver.common.by import By

        source_line = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=confirm-data-meta]").text
        if "Not selected" not in source_line:
            raise AssertionError(f"source field lost Not selected: {source_line}")
        win.assert_run_disabled(
            session.driver,
            "No data source selected yet. Pick one on the confirmation card before running.",
        )
        accept_unlicensed_source(session.driver)
        win.click(session.driver, "[data-testid=confirm-run-start]")
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(session.driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute("data-view")
            == "running"
        )
        shoot("running")
        WebDriverWait(session.driver, 240).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid=completed-screen]"))
        )
        win.assert_no_banner(session.driver, data_root)
        win.assert_no_cjk(session.driver, "[data-testid=completed-screen]", "conclusion page")
        win.export_research_record(session.driver)
        win.wait_css(session.driver, "[data-testid=export-success]")
        session.driver.execute_script(
            "document.querySelector('[data-testid=export-success]')?.scrollIntoView({block:'center'})"
        )
        shoot("conclusion")
        exports = list((data_root / "exports").glob("*"))
        if not exports:
            raise AssertionError("export reported success but exports/ is empty")
        return f"conclusion rendered; wrote {exports[0].name}"

    def step_delete_running() -> str:
        assert session is not None and session.driver is not None
        win.open_confirm_card(session.driver, research_ids["cn"])
        accept_unlicensed_source(session.driver)
        win.click(session.driver, "[data-testid=confirm-run-start]")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        import re

        WebDriverWait(session.driver, 30).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute("data-view")
            == "running"
        )
        rid = research_ids["cn"]
        win.go(session.driver, "#/research")
        running_row = WebDriverWait(session.driver, 20).until(
            lambda d: d.find_element(
                By.CSS_SELECTOR,
                f"[data-testid=research-row][data-research-id='{rid}'][data-status=running]",
            )
        )
        pill = running_row.find_element(By.CSS_SELECTOR, "[data-testid=list-status-pill]")
        if pill.text.strip() != "Running":
            raise AssertionError(f"running row status is {pill.text!r}, expected Running")
        if "+08:00" in running_row.text or re.search(r"[+-]\d{2}:\d{2}", running_row.text):
            raise AssertionError(f"list timestamp must not include a numeric offset, saw {running_row.text}")
        if not re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", running_row.text):
            raise AssertionError(f"expected YYYY-MM-DD HH:mm on the running row, saw {running_row.text}")
        session.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", running_row)
        shoot("before-delete-running", filename="11a-before-delete-running.png")
        row = f"[data-testid=research-row][data-research-id='{rid}'][data-status=running]"
        win.click(session.driver, f"{row} [data-testid=research-row-more]", timeout=15)
        win.click(session.driver, f"{row} [data-testid=delete-research]", timeout=15)
        win.click(session.driver, "[data-testid=in-app-confirm-accept]")
        WebDriverWait(session.driver, 20).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, f"[data-research-id='{rid}']")
        )
        phase = session.driver.find_element(By.CSS_SELECTOR, "[data-testid=night-shell]").get_attribute(
            "data-engine-phase"
        )
        if phase != "running":
            raise AssertionError(f"engine phase after delete is {phase}")
        if not process_running("alphaloop-engine.exe"):
            raise AssertionError("alphaloop-engine exited when a running research was deleted")
        win.assert_no_banner(session.driver, data_root)
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
        assert session.driver is not None
        win.wait_engine(session.driver)
        win.assert_no_banner(session.driver, data_root)
        win.go(session.driver, "#/research")
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        us_id = research_ids["us"]
        cn_id = research_ids["cn"]
        WebDriverWait(session.driver, 20).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, f"[data-research-id='{us_id}']")
        )
        if session.driver.find_elements(By.CSS_SELECTOR, f"[data-research-id='{cn_id}']"):
            raise AssertionError("deleted research reappeared after restart")
        win.click(session.driver, f"[data-testid=research-row][data-research-id='{us_id}'] a")
        win.wait_css(session.driver, "[data-testid=completed-screen]")
        shoot("persist")
        return "completed US research is still listed after restart"

    def step_uninstall() -> str:
        console = ""
        try:
            if session is not None and session.driver is not None and session.proc is not None:
                console = assert_no_controlling_terminal(session.proc.pid)
                win.click(session.driver, "[data-testid=rail-settings]")
                win.wait_css(session.driver, "[data-testid=about-card]")
                shoot("before-uninstall")
                session.close_driver()
        finally:
            if session is not None:
                session.stop_app()
            kill_app()
            remove_product(installed)
        note = "removed the unpacked app bundle"
        if console:
            note = f"{note}; {console}"
        return note

    try:
        run_step("unpack the app archive", "install", step_install)
        run_step("first launch, engine healthy, no traceback", "launch", step_launch)
        run_step("switch zh then en; English rail has no CJK", "language", step_language)
        run_step("secrets: macOS keychain is not locked", "secrets-keyring", step_keyring)
        run_step("secrets: no file is not locked; create passphrase", "secrets-create", step_secrets_create)
        run_step("restart and unlock passphrase", "secrets-unlock", step_secrets_unlock)
        run_step("US and A-share confirm cards open their own research", "confirms", step_two_confirms)
        run_step("blocked Run stays disabled before confirm", "blocked-run", step_blocked_run_before_confirm)
        run_step("momentum intake is hard-blocked, then a re-pick can confirm", "momentum-blocked", step_momentum_blocked)
        run_step(
            "disclosed family buttons and chips share the dialogue handler",
            "family-buttons",
            step_disclosed_family_buttons,
        )
        run_step("English glossary and methods have no CJK", "en-reference", step_english_reference)
        run_step(
            "English time examples 30 minutes and 12 hours parse",
            "en-time-examples",
            step_en_time_examples,
        )
        run_step(
            "English methods and coverage examples parse",
            "en-methods-coverage",
            step_en_methods_coverage,
        )
        run_step(
            "no source selected shows N3, including under the coverage floor",
            "no-source-n3",
            step_no_source_n3,
        )
        run_step(
            "LLM settings form stores the endpoint and vaults the API key",
            "llm-settings",
            step_llm_settings,
        )
        run_step("run to conclusion and export a file", "conclusion", step_run_and_export)
        run_step("delete a running research; engine stays up", "delete-running", step_delete_running)
        run_step("close and reopen; data persists", "persist", step_persist)
    finally:
        if installed is not None:
            previous = blocked
            blocked = None
            run_step("remove the unpacked app", "uninstall", step_uninstall)
            if previous and results[-1].status == "PASS":
                blocked = previous
        if session is not None:
            session.close()
        kill_app()
        win.copy_logs(data_root, app_log)
        write_summary(results)
        win.redact_tree(win.ARTIFACTS)

    failed = [item for item in results if item.status == "FAIL"]
    print(win.redact_text((win.ARTIFACTS / "summary.md").read_text(encoding="utf-8")))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
