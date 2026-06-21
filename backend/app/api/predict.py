"""Prepare the feature vector for a future prostate cancer predictor."""

from fastapi import APIRouter, HTTPException

from app.core.storage import get_case_directory, normalize_case_id
from app.services.prediction_input import prepare_prediction_input
from app.services.radiomics_predict import predict_case_probability


router = APIRouter(tags=["prediction"])


@router.post("/cases/{case_id}/prediction-input")
def build_prediction_input(case_id: str):
    try:
        normalized = normalize_case_id(case_id)
        case_directory = get_case_directory(normalized)
        if not case_directory.exists():
            raise FileNotFoundError("病例不存在。")
        return {"success": True, **prepare_prediction_input(case_directory)}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"预测输入准备失败：{error}") from error


@router.post("/cases/{case_id}/predict")
def predict_case(case_id: str):
    try:
        normalized = normalize_case_id(case_id)
        case_directory = get_case_directory(normalized)
        if not case_directory.exists():
            raise FileNotFoundError("病例不存在。")
        return {"success": True, **predict_case_probability(case_directory)}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"AI 预测失败：{error}") from error

