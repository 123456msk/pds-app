import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def backend_python() -> str:
    candidates = [
        BACKEND_DIR / ".venv" / "python.exe",
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe",
        BACKEND_DIR / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def npm_command() -> str:
    command = "npm.cmd" if os.name == "nt" else "npm"
    resolved = shutil.which(command)
    if not resolved:
        raise RuntimeError("npm was not found. Please install Node.js and npm first.")
    return resolved


def ensure_backend_env() -> None:
    if (BACKEND_DIR / ".venv").exists():
        return
    print("Creating backend virtual environment...")
    subprocess.check_call([sys.executable, "-m", "venv", str(BACKEND_DIR / ".venv")])


def install_backend() -> None:
    ensure_backend_env()
    python = backend_python()
    print("Installing backend dependencies...")
    subprocess.check_call([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND_DIR)
    subprocess.check_call(
        [python, "-m", "pip", "install", "--upgrade", "setuptools", "wheel", "numpy==1.26.2"],
        cwd=BACKEND_DIR,
    )
    subprocess.check_call(
        [python, "-m", "pip", "install", "--no-build-isolation", "-r", "requirements.txt"],
        cwd=BACKEND_DIR,
    )


def install_frontend() -> None:
    print("Installing frontend dependencies...")
    subprocess.check_call([npm_command(), "install"], cwd=FRONTEND_DIR)


def stream_output(name: str, process: subprocess.Popen) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{name}] {line}", end="")


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.terminate()
    else:
        process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def start_services() -> int:
    backend = subprocess.Popen(
        [backend_python(), "-X", "utf8", "run.py"],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    frontend = subprocess.Popen(
        [npm_command(), "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for name, process in [("backend", backend), ("frontend", frontend)]:
        threading.Thread(target=stream_output, args=(name, process), daemon=True).start()

    print("Backend:  http://127.0.0.1:8100/")
    print("Frontend: http://127.0.0.1:5173/")
    print("Press Ctrl+C to stop both services.")

    try:
        while True:
            backend_code = backend.poll()
            frontend_code = frontend.poll()
            if backend_code is not None:
                stop_process(frontend)
                return backend_code
            if frontend_code is not None:
                stop_process(backend)
                return frontend_code
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        print("\nStopping services...")
        stop_process(frontend)
        stop_process(backend)
        return 0


def main() -> int:
    install_backend()
    install_frontend()
    return start_services()


if __name__ == "__main__":
    raise SystemExit(main())
