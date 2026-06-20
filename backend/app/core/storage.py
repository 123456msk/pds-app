"""Atomic case-directory creation and manifest persistence helpers."""

import json
import re
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import CASES_DIR, STAGING_DIR


CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def normalize_case_id(case_id: str | None) -> str:
    value = (case_id or "").strip()
    if not value:
        return uuid.uuid4().hex
    if not CASE_ID_PATTERN.fullmatch(value):
        raise ValueError("case_id 只能包含字母、数字、下划线和短横线，最长 64 位。")
    return value


def get_case_directory(case_id: str) -> Path:
    return CASES_DIR / case_id


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@contextmanager
def staged_case(case_id: str):
    final_directory = get_case_directory(case_id)
    if final_directory.exists():
        raise FileExistsError(f"病例 {case_id} 已存在。")

    staging_directory = STAGING_DIR / f"{case_id}-{uuid.uuid4().hex}"
    staging_directory.mkdir(parents=True)
    try:
        yield staging_directory
        staging_directory.replace(final_directory)
    except Exception:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise
