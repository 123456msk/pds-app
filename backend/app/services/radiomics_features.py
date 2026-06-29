"""PZ/TZ radiomics extraction for prediction input preparation."""

from pathlib import Path

import numpy as np
from radiomics import featureextractor


def _scalar_value(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.size != 1:
            raise ValueError(f"影像组学特征不是标量：shape={value.shape}")
        return value.reshape(-1)[0].item()
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    if hasattr(value, "item"):
        return value.item()
    return float(value)


def _extract_zone(extractor, image_path: Path, mask_path: Path, prefix: str) -> dict:
    result = extractor.execute(str(image_path), str(mask_path))
    features = {}
    for key, value in result.items():
        if key.startswith("diagnostics"):
            continue
        scalar = _scalar_value(value)
        if isinstance(scalar, (int, float)) and not np.isfinite(scalar):
            raise ValueError(f"{prefix}_{key} 得到非法数值：{scalar}")
        features[f"{prefix}_{key}"] = scalar
    if not features:
        raise ValueError(f"{prefix} 未提取到有效影像组学特征。")
    return features


def extract_pz_tz_features(results_directory: Path, params_path: Path) -> tuple[dict, dict]:
    image_path = results_directory / "pet.nii.gz"
    pz_mask = results_directory / "petpz_mask.nii.gz"
    tz_mask = results_directory / "pettz_mask.nii.gz"
    for required in (image_path, pz_mask, tz_mask, params_path):
        if not required.is_file():
            raise FileNotFoundError(f"预测输入文件不存在：{required}")

    extractor = featureextractor.RadiomicsFeatureExtractor(str(params_path))
    pz_features = _extract_zone(extractor, image_path, pz_mask, "PZ")
    tz_features = _extract_zone(extractor, image_path, tz_mask, "TZ")
    merged = {**pz_features, **tz_features}
    return merged, {
        "image": str(image_path),
        "pz_mask": str(pz_mask),
        "tz_mask": str(tz_mask),
        "params": str(params_path),
        "pz_feature_count": len(pz_features),
        "tz_feature_count": len(tz_features),
    }
