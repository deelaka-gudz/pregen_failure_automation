import html
import os
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
AUTOMATION_SCRIPT = ROOT / "automation.py"


def start_automation_process() -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["AUTOMATION_HEADLESS"] = "true"
    env["PYTHONUNBUFFERED"] = "1"

    return subprocess.Popen(
        [sys.executable, str(AUTOMATION_SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def render_logs(log_placeholder) -> None:
    log_lines = st.session_state.logs[-500:]
    if log_lines:
        escaped_logs = "\n".join(
            f'<div class="log-line">{html.escape(line)}</div>' for line in log_lines
        )
    else:
        escaped_logs = '<div class="log-line muted">Logs will appear here after the run starts.</div>'
    log_placeholder.markdown(
        f"""
        <div class="log-panel">
            {escaped_logs}
        </div>
        """,
        unsafe_allow_html=True,
    )


def stream_process_logs(status_placeholder, log_placeholder) -> None:
    process = st.session_state.process
    if process is None:
        process = start_automation_process()
        st.session_state.process = process
        st.session_state.logs = []
        st.session_state.exit_code = None

    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if line:
            for log_line in line.rstrip("\r\n").splitlines() or [""]:
                st.session_state.logs.append(log_line)
            render_logs(log_placeholder)
            continue

        exit_code = process.poll()
        if exit_code is not None:
            for remaining_line in process.stdout:
                for log_line in remaining_line.rstrip("\r\n").splitlines() or [""]:
                    st.session_state.logs.append(log_line)
            st.session_state.exit_code = exit_code
            st.session_state.running = False
            st.session_state.process = None
            break

        time.sleep(0.2)

    render_logs(log_placeholder)
    if st.session_state.exit_code == 0:
        status_placeholder.success("Automation completed")
    else:
        status_placeholder.warning(
            f"Automation stopped with exit code {st.session_state.exit_code}"
        )


st.set_page_config(page_title="PreGen Failure Automation", layout="wide")

st.markdown(
    """
    <style>
    .log-panel {
        height: 350px;
        overflow-y: auto;
        background: #171a22;
        border: 1px solid #2c313d;
        border-radius: 8px;
        padding: 16px 18px;
    }
    .log-line {
        display: block;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        color: #f4f6fb;
        font-size: 14px;
        line-height: 1.55;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }
    .log-line.muted {
        color: #9aa4b2;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("PreGen Failure Automation")
st.caption("Runs the Helm automation in headless browser mode and streams logs here.")

if not AUTOMATION_SCRIPT.exists():
    st.error(f"Could not find {AUTOMATION_SCRIPT.name}.")
    st.stop()

if "running" not in st.session_state:
    st.session_state.running = False
if "process" not in st.session_state:
    st.session_state.process = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "exit_code" not in st.session_state:
    st.session_state.exit_code = None

start = st.button(
    "Start automation",
    type="primary",
    disabled=st.session_state.running,
)

if start:
    st.session_state.running = True
    st.session_state.process = None
    st.session_state.logs = []
    st.session_state.exit_code = None
    st.rerun()

status_placeholder = st.empty()
if st.session_state.running:
    status_placeholder.info("Automation running...")
elif st.session_state.exit_code == 0:
    status_placeholder.success("Automation completed")
elif st.session_state.exit_code is not None:
    status_placeholder.warning(
        f"Automation stopped with exit code {st.session_state.exit_code}"
    )
else:
    status_placeholder.info("Ready to start")

log_placeholder = st.empty()
render_logs(log_placeholder)

if st.session_state.running:
    stream_process_logs(status_placeholder, log_placeholder)
