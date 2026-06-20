"""Persist complete selected DICOM series and their original NIfTI volumes."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from app.core.storage import get_case_directory, normalize_case_id, staged_case, write_json
from .dicom_processing import (
    extract_dicom_zip,
    is_ct,
    is_pet,
    is_t2_mri,
    prepare_volume,
    validate_closed_range,
)


def calculate_pet_range(start_ct: int, end_ct: int, ct_count: int, pet_count: int) -> dict:
    if ct_count <= 0 or pet_count <= 0:
        raise ValueError("CT/PET 序列张数必须大于 0。")
    ratio = pet_count / ct_count
    start = max(1, int(start_ct * ratio + 0.5))
    end = min(pet_count, int(end_ct * ratio + 0.5))
    if start > end:
        raise ValueError("CT 范围换算后的 PET 范围为空。")
    return {"start": start, "end": end, "ratio": ratio}


def _save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as target:
        shutil.copyfileobj(upload.file, target)


def prepare_case_data(
    mri_zip: UploadFile,
    psma_zip: UploadFile,
    start_mri: int,
    end_mri: int,
    start_ct: int,
    end_ct: int,
    patient_name: str,
    age: int,
    psa: float,
    ft_psa: float,
    case_id: str | None,
) -> dict:
    validate_closed_range(start_mri, end_mri, "MRI")
    validate_closed_range(start_ct, end_ct, "CT")
    patient_name = patient_name.strip()
    if not patient_name:
        raise ValueError("病人姓名不能为空。")
    if age < 0 or age > 120:
        raise ValueError("年龄必须在 0 到 120 岁之间。")
    if psa < 0 or ft_psa < 0:
        raise ValueError("PSA 和 f/tPSA 不能为负数。")
    normalized_case_id = normalize_case_id(case_id)

    with staged_case(normalized_case_id) as case_directory:
        upload_directory = case_directory / "uploads"
        mri_zip_path = upload_directory / "mri.zip"
        psma_zip_path = upload_directory / "psma.zip"
        _save_upload(mri_zip, mri_zip_path)
        _save_upload(psma_zip, psma_zip_path)

        extraction_directory = case_directory / ".extracted"
        mri_records = extract_dicom_zip(mri_zip_path, extraction_directory / "mri")
        psma_records = extract_dicom_zip(psma_zip_path, extraction_directory / "psma")

        volumes = {
            "mri": prepare_volume(
                mri_records,
                is_t2_mri,
                start_mri,
                end_mri,
                "T2W MRI",
                "mri",
                case_directory,
            ),
            "ct": prepare_volume(
                psma_records,
                is_ct,
                start_ct,
                end_ct,
                "CT",
                "ct",
                case_directory,
            ),
            "pet": prepare_volume(
                psma_records,
                is_pet,
                start_ct,
                end_ct,
                "PET",
                "pet",
                case_directory,
            ),
        }
        ct_positions = [
            position
            for position, index in enumerate(volumes["ct"]["ordered_indices"])
            if index is not None and start_ct <= index <= end_ct
        ]
        if not ct_positions:
            raise ValueError(f"CT 在闭区间 [{start_ct}, {end_ct}] 内没有匹配文件。")
        ct_count = len(volumes["ct"]["ordered_filenames"])
        pet_count = len(volumes["pet"]["ordered_filenames"])
        pet_range = calculate_pet_range(start_ct, end_ct, ct_count, pet_count)
        ratio = pet_range["ratio"]
        pet_start = pet_range["start"]
        pet_end = pet_range["end"]
        pet_positions = list(range(pet_start - 1, pet_end))
        volumes["pet"]["range_selected_indices"] = [
            volumes["pet"]["ordered_indices"][position]
            for position in pet_positions
            if volumes["pet"]["ordered_indices"][position] is not None
        ]
        volumes["pet"]["calculated_position_range"] = {
            "start": pet_start,
            "end": pet_end,
            "ratio": ratio,
        }
        ranges = {
            "mri": {"start": start_mri, "end": end_mri},
            "ct": {"start": start_ct, "end": end_ct},
            "pet": {"start": pet_start, "end": pet_end, "ratio": ratio},
        }
        shutil.rmtree(extraction_directory, ignore_errors=True)

        manifest = {
            "case_id": normalized_case_id,
            "status": "prepared",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "patient": {
                "name": patient_name,
                "age": age,
                "psa": psa,
                "ft_psa": ft_psa,
            },
            "ranges": ranges,
            "index_rule": "MRI/CT 按文件名第一个数字取闭区间",
            "pipeline_rule": "完整 T2 MRI 输入模型；MRI/CT/PET 范围用于分割后的裁剪和映射",
            "volumes": volumes,
        }
        write_json(case_directory / "manifest.json", manifest)

    final_directory = get_case_directory(normalized_case_id)
    return {
        "success": True,
        "case_id": normalized_case_id,
        "case_directory": str(final_directory),
        "manifest_path": str(final_directory / "manifest.json"),
        "patient": {"name": patient_name, "age": age, "psa": psa, "ft_psa": ft_psa},
        "ranges": ranges,
        "volumes": volumes,
    }
