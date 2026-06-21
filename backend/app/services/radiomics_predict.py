"""Load the trained GBDT pipeline and return malignant-class probability."""

import json
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from app.core.storage import write_json
from app.services.prediction_input import prepare_prediction_input


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "prediction" / "prostate_cancer_pipeline.pkl"
PREDICTION_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def load_prediction_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"预测模型不存在：{MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def predict_case_probability(case_directory: Path) -> dict:
    preparation = prepare_prediction_input(case_directory)
    input_path = Path(preparation["json_path"])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    extracted = payload["features"]
    model = load_prediction_model()
    expected_names = list(model.feature_names_in_)
    extracted_names = list(extracted)
    missing = [name for name in expected_names if name not in extracted]
    unexpected = [name for name in extracted_names if name not in expected_names]
    if missing or unexpected:
        raise ValueError(
            f"预测特征与模型不一致：缺少 {len(missing)} 项，多出 {len(unexpected)} 项。"
            f" missing={missing[:5]}, unexpected={unexpected[:5]}"
        )
    frame = pd.DataFrame([[extracted[name] for name in expected_names]], columns=expected_names)
    with PREDICTION_LOCK:
        probabilities = model.predict_proba(frame)[0]
    classes = [value.item() if hasattr(value, "item") else value for value in model.classes_]
    if 1 not in classes:
        raise ValueError(f"模型类别中不存在恶性标签 1：{classes}")
    malignant_probability = float(probabilities[classes.index(1)])
    created_at = datetime.now(timezone.utc).isoformat()
    result = {
        "case_id": case_directory.name,
        "created_at": created_at,
        "malignant_probability": malignant_probability,
        "probability_percent": malignant_probability * 100.0,
        "model_classes": classes,
        "feature_count": len(expected_names),
        "excluded_features": ["volume_ml"],
        "model_path": str(MODEL_PATH),
    }
    output_path = case_directory / "prediction" / "prediction_result.json"
    write_json(output_path, result)
    manifest_path = case_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["prediction"] = {
        "created_at": created_at,
        "malignant_probability": malignant_probability,
        "result_path": str(output_path),
    }
    write_json(manifest_path, manifest)
    return result

