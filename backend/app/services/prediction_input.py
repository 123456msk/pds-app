"""Build and persist the final feature vector consumed by a future predictor."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.storage import write_json
from app.services.clinical_features import CLINICAL_FEATURE_ORDER, build_clinical_features
from app.services.radiomics_features import extract_pz_tz_features


RADIOMICS_PARAMS = Path(__file__).resolve().parents[1] / "models" / "prediction" / "radiomics_params.yaml"
MODEL_CLINICAL_FEATURE_ORDER = [name for name in CLINICAL_FEATURE_ORDER if name != "volume_ml"]


def _load_manifest(case_directory: Path) -> dict:
    manifest_path = case_directory / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("病例不存在或尚未准备完成。")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def merge_prediction_features(radiomics: dict, clinical: dict) -> dict:
    """Match the training-table merge order: radiomics columns, then JSON features."""
    merged = dict(radiomics)
    for name in MODEL_CLINICAL_FEATURE_ORDER:
        merged[name] = clinical[name]
    return merged

def prepare_prediction_input(case_directory: Path) -> dict:
    manifest = _load_manifest(case_directory)
    if manifest.get("status") != "completed":
        raise ValueError("病例必须完成分割与映射后才能准备预测输入。")
    results_directory = case_directory / "results"
    clinical, clinical_details = build_clinical_features(manifest.get("patient", {}), results_directory)
    radiomics, radiomics_details = extract_pz_tz_features(results_directory, RADIOMICS_PARAMS)

    features = merge_prediction_features(radiomics, clinical)
    feature_names = list(features)
    values = [features[name] for name in feature_names]
    if any(value is None for value in values):
        missing = [name for name, value in features.items() if value is None]
        raise ValueError(f"预测输入包含空值：{missing}")

    output_directory = case_directory / "prediction"
    output_directory.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "case_id": manifest["case_id"],
        "created_at": created_at,
        "merge_order": "PZ/TZ radiomics first, then USE_JSON_FEATURES",
        "clinical_feature_names": MODEL_CLINICAL_FEATURE_ORDER,
        "calculated_but_excluded_features": ["volume_ml"],
        "radiomics_feature_count": len(radiomics),
        "feature_count": len(features),
        "feature_names": feature_names,
        "values": values,
        "features": features,
        "sources": {
            "clinical": clinical_details,
            "radiomics": radiomics_details,
        },
    }
    json_path = output_directory / "input_features.json"
    csv_path = output_directory / "input_features.csv"
    clinical_path = output_directory / "clinical_features.json"
    radiomics_path = output_directory / "radiomics_features.json"
    write_json(json_path, payload)
    write_json(clinical_path, {"features": clinical, "details": clinical_details})
    write_json(radiomics_path, {"features": radiomics, "details": radiomics_details})
    csv_written = True
    try:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(feature_names)
            writer.writerow(values)
    except PermissionError:
        csv_written = False

    manifest["prediction_input"] = {
        "created_at": created_at,
        "feature_count": len(features),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }
    write_json(case_directory / "manifest.json", manifest)
    return {
        "case_id": manifest["case_id"],
        "feature_count": len(features),
        "clinical_features": clinical,
        "radiomics_feature_count": len(radiomics),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }





