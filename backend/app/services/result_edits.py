"""Persist viewer-edited MRI/PET zone masks and rebuild the case archive."""

import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import SimpleITK as sitk

from app.core.storage import write_json


EDITABLE_MASKS = {
    "mripz_mask.nii.gz": "mri.nii.gz",
    "mritz_mask.nii.gz": "mri.nii.gz",
    "petpz_mask.nii.gz": "pet.nii.gz",
    "pettz_mask.nii.gz": "pet.nii.gz",
}


def _validate_mask(mask_path: Path, image_path: Path) -> None:
    mask = sitk.ReadImage(str(mask_path))
    image = sitk.ReadImage(str(image_path))
    if mask.GetSize() != image.GetSize():
        raise ValueError(
            f"{mask_path.name} 尺寸 {mask.GetSize()} 与 {image_path.name} {image.GetSize()} 不一致。"
        )


def save_edited_masks(case_directory: Path, payloads: dict[str, bytes]) -> dict:
    if set(payloads) != set(EDITABLE_MASKS):
        raise ValueError("必须同时提交 MRI/PET 的 PZ、TZ 四个掩膜。")

    results_directory = case_directory / "results"
    if not results_directory.exists():
        raise FileNotFoundError("病例结果尚未生成。")

    with tempfile.TemporaryDirectory(dir=case_directory) as temporary:
        temporary_directory = Path(temporary)
        for filename, image_filename in EDITABLE_MASKS.items():
            candidate = temporary_directory / filename
            candidate.write_bytes(payloads[filename])
            _validate_mask(candidate, results_directory / image_filename)

        for filename in EDITABLE_MASKS:
            (results_directory / filename).write_bytes((temporary_directory / filename).read_bytes())

    archive_path = case_directory / "results.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result_path in sorted(results_directory.iterdir()):
            if result_path.is_file():
                archive.write(result_path, arcname=result_path.name)

    manifest_path = case_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    saved_at = datetime.now(timezone.utc).isoformat()
    manifest["viewer_edits"] = {
        "saved_at": saved_at,
        "files": sorted(EDITABLE_MASKS),
    }
    write_json(manifest_path, manifest)
    return {"saved_at": saved_at, "files": sorted(EDITABLE_MASKS)}

