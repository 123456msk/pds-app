"""Run full-volume MRI segmentation and multimodal mapping."""

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import PERSISTENT_SEGMENTATION_WORKER, SEGMENTATION_MODEL_DIR
from app.core.storage import write_json
from app.services.multimodal_mapping import build_multimodal_results

SEGMENTATION_LOCK = threading.Lock()
WORKER_LOCK = threading.Lock()
WORKER_PROCESS: subprocess.Popen | None = None


def _load_manifest(case_directory: Path) -> dict:
    manifest_path = case_directory / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("病例尚未完成影像准备。")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _worker_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "models" / name


def _read_worker_json(process: subprocess.Popen) -> dict:
    while True:
        line = process.stdout.readline()
        if line == "":
            raise RuntimeError("分割 worker 已退出。")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") in {"ready", "result", "bye"}:
            return payload


def _get_worker() -> subprocess.Popen:
    global WORKER_PROCESS
    if WORKER_PROCESS and WORKER_PROCESS.poll() is None:
        return WORKER_PROCESS

    command = [
        sys.executable,
        "-X",
        "utf8",
        str(_worker_path("segmentation_server.py")),
        "--model-dir",
        str(SEGMENTATION_MODEL_DIR),
    ]
    WORKER_PROCESS = subprocess.Popen(
        command,
        cwd=Path(__file__).resolve().parents[2],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    ready = _read_worker_json(WORKER_PROCESS)
    if ready.get("type") != "ready":
        raise RuntimeError(f"分割 worker 启动异常：{ready}")
    return WORKER_PROCESS


def _run_with_persistent_worker(case_directory: Path, case_id: str) -> dict:
    with WORKER_LOCK:
      process = _get_worker()
      request = json.dumps({"case_dir": str(case_directory), "case_id": case_id}, ensure_ascii=False)
      process.stdin.write(request + "\n")
      process.stdin.flush()
      response = _read_worker_json(process)
      if not response.get("ok"):
          global WORKER_PROCESS
          try:
              process.kill()
          except Exception:
              pass
          WORKER_PROCESS = None
          raise RuntimeError(response.get("error") or "分割 worker 执行失败。")
      return response


def _run_with_one_shot_worker(case_directory: Path, case_id: str) -> dict:
    worker_path = _worker_path("segmentation_worker.py")
    command = [
        sys.executable, "-X", "utf8", str(worker_path),
        "--model-dir", str(SEGMENTATION_MODEL_DIR),
        "--case-dir", str(case_directory), "--case-id", case_id,
    ]
    completed = subprocess.run(
        command, cwd=Path(__file__).resolve().parents[2], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=4 * 60 * 60,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "error": f"MRI 分割失败，退出码 {completed.returncode}。",
        }
    return {
        "ok": True,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "result": json.loads((case_directory / "segmentation" / "worker_result.json").read_text(encoding="utf-8")),
    }


def run_case_segmentation(case_directory: Path) -> dict:
    manifest = _load_manifest(case_directory)
    case_id = manifest["case_id"]
    segmentation_directory = case_directory / "segmentation"
    segmentation_directory.mkdir(parents=True, exist_ok=True)
    log_path = segmentation_directory / "segmentation.log"
    manifest["status"] = "segmenting"
    manifest["segmentation_started_at"] = datetime.now(timezone.utc).isoformat()
    write_json(case_directory / "manifest.json", manifest)

    try:
        with SEGMENTATION_LOCK:
            try:
                worker_response = _run_with_persistent_worker(case_directory, case_id) if PERSISTENT_SEGMENTATION_WORKER else _run_with_one_shot_worker(case_directory, case_id)
            except Exception:
                worker_response = _run_with_one_shot_worker(case_directory, case_id)
        log_path.write_text(
            worker_response.get("stdout", "") + "\n--- STDERR ---\n" + worker_response.get("stderr", ""),
            encoding="utf-8",
        )
        if not worker_response.get("ok"):
            raise RuntimeError(f"{worker_response.get('error', 'MRI 分割失败')} 详情见 {log_path}")

        segmentation = worker_response.get("result") or json.loads((segmentation_directory / "worker_result.json").read_text(encoding="utf-8"))
        segmentation["log_path"] = str(log_path)
        segmentation["multimodal"] = build_multimodal_results(case_directory)
        manifest["status"] = "completed"
        manifest["segmentation_completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["segmentation"] = segmentation
        write_json(case_directory / "manifest.json", manifest)
        return segmentation
    except Exception as error:
        manifest["status"] = "segmentation_failed"
        manifest["segmentation_error"] = str(error)
        write_json(case_directory / "manifest.json", manifest)
        raise
