"""Full MRI segmentation and MRI-to-CT-to-PET mapping endpoint."""

from fastapi import APIRouter, HTTPException

from app.core.schemas import SegmentationResponse
from app.core.storage import get_case_directory, normalize_case_id
from app.services.segmentation import run_case_segmentation

router = APIRouter(tags=["segmentation"])


@router.post("/cases/{case_id}/segment", response_model=SegmentationResponse)
def segment_case(case_id: str):
    try:
        normalized = normalize_case_id(case_id)
        case_directory = get_case_directory(normalized)
        if not case_directory.exists():
            raise FileNotFoundError("病例不存在。")
        return {"success": True, "case_id": normalized, "segmentation": run_case_segmentation(case_directory)}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"自动分割失败：{error}") from error