import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from livekit import api

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
AGENT_SCRIPT_RELATIVE = Path("src") / "agent.py"
AGENT_SCRIPT = PROJECT_ROOT / AGENT_SCRIPT_RELATIVE
LOG_FILE = BASE_DIR / "agent.log"
STARTUP_GRACE_SECONDS = 1.5
STARTUP_ESTIMATE_SECONDS = 10
DEFAULT_AGENT_MODE = os.getenv("AGENT_RUN_MODE", "start").strip() or "start"
DEFAULT_ROOM_PREFIX = "voice-room"
DEFAULT_AGENT_NAME = "my-agent"

load_dotenv(PROJECT_ROOT / ".env.local")

app = FastAPI(title="Voice Agent Control Panel")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

agent_process: subprocess.Popen | None = None
process_lock = Lock()
recent_logs: deque[str] = deque(maxlen=80)
last_status_message = "Ready."
last_exit_code: int | None = None
startup_started_at: float | None = None


class LiveKitTokenRequest(BaseModel):
    room_name: str | None = None
    participant_name: str | None = None


def sanitize_name(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback

    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-")
    return sanitized[:64] or fallback


def build_room_name(room_name: str | None) -> str:
    fallback = f"{DEFAULT_ROOM_PREFIX}-{uuid4().hex[:8]}"
    return sanitize_name(room_name, fallback)


def build_participant_identity(participant_name: str | None) -> tuple[str, str]:
    display_name = (participant_name or "").strip() or "Web User"
    identity = sanitize_name(display_name.lower(), f"user-{uuid4().hex[:8]}")
    return identity, display_name[:80]


def get_livekit_url() -> str:
    livekit_url = (os.getenv("LIVEKIT_URL") or "").strip()
    if not livekit_url:
        raise HTTPException(status_code=500, detail="LIVEKIT_URL is missing from environment.")
    return livekit_url


def create_livekit_token(room_name: str, identity: str, display_name: str) -> str:
    token = (
        api.AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
        .with_identity(identity)
        .with_name(display_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                name=room_name,
                agents=[
                    api.RoomAgentDispatch(agent_name=DEFAULT_AGENT_NAME),
                ],
            )
        )
    )
    return token.to_jwt()


def derive_runtime_state() -> tuple[str, str]:
    logs = list(recent_logs)

    for line in reversed(logs):
        if "received user transcript" in line:
            return "ready", "Assistant is live and processing voice input."
        if "registered worker" in line:
            return "ready", "Assistant is ready and waiting for a connection."
        if "starting worker" in line:
            return "starting", "Starting the model and preparing the voice worker."

    if startup_started_at is not None:
        return "starting", "Starting the model and preparing the voice worker."

    return "online", last_status_message


def get_startup_remaining_seconds() -> int | None:
    if startup_started_at is None:
        return None

    elapsed = time.monotonic() - startup_started_at
    remaining = max(0, STARTUP_ESTIMATE_SECONDS - int(elapsed))
    return remaining


def resolve_python_executable() -> str:
    configured = os.getenv("CONTROL_PANEL_PYTHON")
    candidates = [
        configured,
        str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"),
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        sys.executable,
        shutil.which("python"),
        shutil.which("python3"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    raise RuntimeError("No Python interpreter was found for starting the agent.")


def set_status(message: str) -> None:
    global last_status_message
    last_status_message = message


def append_log(line: str) -> None:
    cleaned = line.rstrip()
    if not cleaned:
        return

    recent_logs.append(cleaned)

    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(cleaned + "\n")


def capture_process_output(proc: subprocess.Popen) -> None:
    global last_exit_code, startup_started_at

    if proc.stdout is None:
        return

    for line in proc.stdout:
        with process_lock:
            append_log(line)

    exit_code = proc.wait()

    with process_lock:
        last_exit_code = exit_code
        startup_started_at = None
        if agent_process is proc:
            if exit_code == 0:
                set_status("Agent stopped.")
            else:
                details = recent_logs[-1] if recent_logs else f"Exit code: {exit_code}"
                set_status(f"Agent stopped unexpectedly. {details}")


def is_agent_running() -> bool:
    return agent_process is not None and agent_process.poll() is None


def build_agent_command() -> list[str]:
    return [resolve_python_executable(), str(AGENT_SCRIPT_RELATIVE), DEFAULT_AGENT_MODE]


def build_agent_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.setdefault("TERM", "xterm-256color")
    return env


def start_log_reader(proc: subprocess.Popen) -> None:
    reader = Thread(target=capture_process_output, args=(proc,), daemon=True)
    reader.start()


def kill_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def stop_agent_process(timeout: int = 10) -> None:
    global agent_process, last_exit_code, startup_started_at

    if agent_process is None:
        return

    proc = agent_process

    if proc.poll() is not None:
        last_exit_code = proc.returncode
        agent_process = None
        startup_started_at = None
        return

    if os.name == "nt":
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        except Exception:
            proc.terminate()
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_process_tree(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    last_exit_code = proc.returncode
    agent_process = None
    startup_started_at = None
    set_status("Agent stopped.")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status")
async def status() -> JSONResponse:
    global agent_process, last_exit_code, startup_started_at

    with process_lock:
        running = is_agent_running()
        message = last_status_message
        phase = "offline"
        startup_remaining_seconds = None

        if not running and agent_process is not None:
            last_exit_code = agent_process.returncode
            agent_process = None
            startup_started_at = None
        elif running:
            phase, message = derive_runtime_state()
            startup_remaining_seconds = get_startup_remaining_seconds() if phase == "starting" else None

        return JSONResponse(
            {
                "running": running,
                "message": message,
                "exit_code": last_exit_code,
                "mode": DEFAULT_AGENT_MODE,
                "phase": phase,
                "startup_remaining_seconds": startup_remaining_seconds,
                "startup_estimate_seconds": STARTUP_ESTIMATE_SECONDS,
            }
        )


@app.get("/logs")
async def logs() -> JSONResponse:
    with process_lock:
        return JSONResponse({"lines": list(recent_logs)})


@app.post("/livekit/token")
async def livekit_token(payload: LiveKitTokenRequest) -> JSONResponse:
    if not is_agent_running():
        raise HTTPException(status_code=409, detail="Start the agent before connecting from the browser.")

    room_name = build_room_name(payload.room_name)
    identity, display_name = build_participant_identity(payload.participant_name)
    livekit_url = get_livekit_url()

    try:
        token = create_livekit_token(room_name, identity, display_name)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse(
        {
            "url": livekit_url,
            "token": token,
            "room_name": room_name,
            "participant_name": display_name,
            "identity": identity,
        }
    )


@app.post("/start")
async def start() -> JSONResponse:
    global agent_process, last_exit_code, startup_started_at

    with process_lock:
        if is_agent_running():
            return JSONResponse(
                {
                    "running": True,
                    "message": f"Agent is already running in {DEFAULT_AGENT_MODE} mode.",
                    "exit_code": last_exit_code,
                    "mode": DEFAULT_AGENT_MODE,
                }
            )

        if not AGENT_SCRIPT.exists():
            raise HTTPException(status_code=500, detail=f"Agent script not found: {AGENT_SCRIPT}")

        command = build_agent_command()
        env = build_agent_environment()
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

        recent_logs.clear()
        LOG_FILE.write_text("", encoding="utf-8")
        last_exit_code = None
        startup_started_at = time.monotonic()
        set_status(f"Starting agent in {DEFAULT_AGENT_MODE} mode...")

        try:
            agent_process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                env=env,
                creationflags=creationflags,
                start_new_session=(os.name != "nt"),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            set_status(f"Failed to start agent. {exc}")
            raise HTTPException(status_code=500, detail=f"Failed to start agent: {exc}") from exc

        start_log_reader(agent_process)

    time.sleep(STARTUP_GRACE_SECONDS)

    with process_lock:
        if not is_agent_running():
            exit_code = agent_process.returncode if agent_process is not None else last_exit_code
            message = recent_logs[-1] if recent_logs else "Agent exited right after startup."
            set_status(message)
            agent_process = None
            startup_started_at = None
            return JSONResponse(
                {
                    "running": False,
                    "message": message,
                    "exit_code": exit_code,
                    "mode": DEFAULT_AGENT_MODE,
                    "phase": "offline",
                    "startup_remaining_seconds": None,
                    "startup_estimate_seconds": STARTUP_ESTIMATE_SECONDS,
                },
                status_code=500,
            )

        phase, runtime_message = derive_runtime_state()
        set_status(runtime_message)
        return JSONResponse(
            {
                "running": True,
                "message": last_status_message,
                "exit_code": last_exit_code,
                "mode": DEFAULT_AGENT_MODE,
                "phase": phase,
                "startup_remaining_seconds": get_startup_remaining_seconds() if phase == "starting" else None,
                "startup_estimate_seconds": STARTUP_ESTIMATE_SECONDS,
            }
        )


@app.post("/stop")
async def stop() -> JSONResponse:
    global agent_process, startup_started_at

    with process_lock:
        if not is_agent_running():
            if agent_process is not None and agent_process.poll() is not None:
                agent_process = None
            startup_started_at = None
            set_status("Agent is not running.")
            return JSONResponse(
                {
                    "running": False,
                    "message": last_status_message,
                    "exit_code": last_exit_code,
                    "mode": DEFAULT_AGENT_MODE,
                    "phase": "offline",
                    "startup_remaining_seconds": None,
                    "startup_estimate_seconds": STARTUP_ESTIMATE_SECONDS,
                }
            )

        stop_agent_process()

    return JSONResponse(
        {
            "running": False,
            "message": last_status_message,
            "exit_code": last_exit_code,
            "mode": DEFAULT_AGENT_MODE,
            "phase": "offline",
            "startup_remaining_seconds": None,
            "startup_estimate_seconds": STARTUP_ESTIMATE_SECONDS,
        }
    )


@app.on_event("shutdown")
def on_shutdown() -> None:
    with process_lock:
        stop_agent_process()
