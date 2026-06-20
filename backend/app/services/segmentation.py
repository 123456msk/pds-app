"""Run full-volume MRI segmentation and multimodal mapping."""

import json
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import SEGMENTATION_MODEL_DIR
from app.core.storage import write_json
from app.services.multimodal_mapping import build_multimodal_results

SEGMENTATION_LOCK = threading.Lock()


def _load_manifest(case_directory: Path) -> dict:
    manifest_path = case_directory / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("病例尚未完成影像准备。")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def run_case_segmentation(case_directory: Path) -> dict:
    manifest = _load_manifest(case_directory)
    case_id = manifest["case_id"]
    segmentation_directory = case_directory / "segmentation"
    segmentation_directory.mkdir(parents=True, exist_ok=True)
    log_path = segmentation_directory / "segmentation.log"
    manifest["status"] = "segmenting"
    manifest["segmentation_started_at"] = datetime.now(timezone.utc).isoformat()
    write_json(case_directory / "manifest.json", manifest)

    worker_path = Path(__file__).resolve().parents[1] / "models" / "segmentation_worker.py"
    command = [
        sys.executable, "-X", "utf8", str(worker_path),
        "--model-dir", str(SEGMENTATION_MODEL_DIR),
        "--case-dir", str(case_directory), "--case-id", case_id,
    ]
    try:
        with SEGMENTATION_LOCK:
            completed = subprocess.run(
                command, cwd=Path(__file__).resolve().parents[2], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=4 * 60 * 60,
            )
        log_path.write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"MRI 分割失败，退出码 {completed.returncode}。详情见 {log_path}")

        segmentation = json.loads((segmentation_directory / "worker_result.json").read_text(encoding="utf-8"))
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