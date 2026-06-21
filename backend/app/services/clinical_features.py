"""Clinical and mask-derived features used by the prediction pipeline."""

from pathlib import Path

import numpy as np
import SimpleITK as sitk


CLINICAL_FEATURE_ORDER = [
    "age",
    "PSA",
    "f_tPSA",
    "volume_ml",
    "high_volume_ml",
    "psad",
    "tzv",
    "pzv",
    "pzratio",
]


def calculate_mask_volume(mask_path: Path) -> dict:
    image = sitk.ReadImage(str(mask_path))
    array = sitk.GetArrayFromImage(image)
    spacing = image.GetSpacing()
    voxel_volume_mm3 = float(np.prod(spacing))
    voxel_count = int(np.count_nonzero(array > 0))
    return {
        "volume_ml": float(voxel_count * voxel_volume_mm3 / 1000.0),
        "mask_voxels": voxel_count,
        "spacing": [float(value) for value in spacing],
        "shape": list(array.shape),
    }


def compute_zone_volumes(wg: dict, tz: dict, pz: dict, pz_thresh: float = 1.0, tz_thresh: float = 1.0) -> dict:
    whole_volume = float(wg["volume_ml"])
    tz_raw = float(tz["volume_ml"])
    pz_raw = float(pz["volume_ml"])
    if tz_raw < tz_thresh:
        raise ValueError(f"TZ 体积过小，无法准备预测输入：{tz_raw:.4f} mL")
    if pz_raw < pz_thresh:
        pz_volume = max(whole_volume - tz_raw, 0.0)
        method = "WG-TZ"
    else:
        pz_volume = pz_raw
        method = "PZ_MASK"
    return {
        "tzv": tz_raw,
        "pzv": pz_volume,
        "pzratio": pz_volume / whole_volume if whole_volume > 0 else None,
        "tzv_raw": tz_raw,
        "pzv_raw": pz_raw,
        "pzv_method": method,
    }


def calculate_high_pet_volume(pet_path: Path, mask_path: Path, percentile: float = 95.0) -> dict:
    pet_image = sitk.ReadImage(str(pet_path))
    mask_image = sitk.ReadImage(str(mask_path))
    pet_array = sitk.GetArrayFromImage(pet_image)
    mask_array = sitk.GetArrayFromImage(mask_image)
    if pet_array.shape != mask_array.shape:
        raise ValueError(f"PET 与 WG 掩膜尺寸不一致：{pet_array.shape} != {mask_array.shape}")
    valid_values = pet_array[mask_array > 0]
    if valid_values.size == 0:
        raise ValueError("PET WG 掩膜为空。")
    threshold = float(np.percentile(valid_values, percentile))
    high_voxels = int(np.count_nonzero((pet_array > threshold) & (mask_array > 0)))
    voxel_volume_mm3 = float(np.prod(pet_image.GetSpacing()))
    return {
        "percentile": float(percentile),
        "threshold": threshold,
        "high_voxels": high_voxels,
        "high_volume_ml": float(high_voxels * voxel_volume_mm3 / 1000.0),
    }


def build_clinical_features(patient: dict, results_directory: Path) -> tuple[dict, dict]:
    required_patient = {"age", "psa", "ft_psa"}
    missing_patient = required_patient - set(patient)
    if missing_patient:
        raise ValueError(f"患者信息缺少字段：{sorted(missing_patient)}")

    wg = calculate_mask_volume(results_directory / "mriwg_mask.nii.gz")
    tz = calculate_mask_volume(results_directory / "mritz_mask.nii.gz")
    pz = calculate_mask_volume(results_directory / "mripz_mask.nii.gz")
    zones = compute_zone_volumes(wg, tz, pz)
    pet_high = calculate_high_pet_volume(
        results_directory / "pet.nii.gz",
        results_directory / "petwg_mask.nii.gz",
    )
    volume_ml = float(wg["volume_ml"])
    psa = float(patient["psa"])
    if volume_ml <= 0:
        raise ValueError("MRI WG 体积必须大于 0。")
    features = {
        "age": float(patient["age"]),
        "PSA": psa,
        "f_tPSA": float(patient["ft_psa"]),
        "volume_ml": volume_ml,
        "high_volume_ml": float(pet_high["high_volume_ml"]),
        "psad": psa / volume_ml,
        "tzv": float(zones["tzv"]),
        "pzv": float(zones["pzv"]),
        "pzratio": float(zones["pzratio"]),
    }
    details = {
        "feature_sources": {
            "age": "manifest.patient.age",
            "PSA": "manifest.patient.psa",
            "f_tPSA": "manifest.patient.ft_psa",
            "volume_ml": "MRI mriwg_mask.nii.gz",
            "high_volume_ml": "PET pet.nii.gz within petwg_mask.nii.gz, values above masked 95th percentile",
            "psad": "PSA / MRI WG volume_ml",
            "tzv": "MRI mritz_mask.nii.gz",
            "pzv": "MRI mripz_mask.nii.gz; fallback MRI WG - MRI TZ when PZ < 1 mL",
            "pzratio": "MRI pzv / MRI WG volume_ml",
        },
        "mri_wg": wg,
        "mri_tz": tz,
        "mri_pz": pz,
        "mri_zones": zones,
        "pet_high": pet_high,
    }
    return features, details

