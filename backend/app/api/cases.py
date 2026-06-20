"""HTTP endpoints for case creation, DICOM upload, and case metadata."""

import json
import zipfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.schemas import PreparedCaseResponse
from app.core.storage import get_case_directory, normalize_case_id
from app.services.case_preparation import prepare_case_data
from app.services.result_edits import save_edited_masks


router = APIRouter(tags=["cases"])


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    try:
        normalized = normalize_case_id(case_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    manifest_path = get_case_directory(normalized) / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="病例不存在。")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@router.get("/cases/{case_id}/results")
def download_case_results(case_id: str):
    try:
        normalized = normalize_case_id(case_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    archive_path = get_case_directory(normalized) / "results.zip"
    if not archive_path.exists():
        raise HTTPException(status_code=404, detail="病例最终结果尚未生成。")
    return FileResponse(archive_path, media_type="application/zip", filename=f"{normalized}_12_results.zip")

RESULT_FILES = {
    "mri.nii.gz", "mripz_mask.nii.gz", "mritz_mask.nii.gz",
    "pet.nii.gz", "petpz_mask.nii.gz", "pettz_mask.nii.gz",
    "ct.nii.gz", "ctpz_mask.nii.gz", "cttz_mask.nii.gz",
    "mriwg_mask.nii.gz", "ctwg_mask.nii.gz", "petwg_mask.nii.gz",
}


@router.get("/cases/{case_id}/results/{filename}")
def get_result_file(case_id: str, filename: str):
    try:
        normalized = normalize_case_id(case_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if filename not in RESULT_FILES:
        raise HTTPException(status_code=400, detail="不允许访问该结果文件。")
    result_path = get_case_directory(normalized) / "results" / filename
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在。")
    return FileResponse(result_path, media_type="application/octet-stream", filename=filename)

@router.post("/cases/{case_id}/viewer-masks")
async def save_viewer_masks(
    case_id: str,
    mripz_mask: UploadFile = File(...),
    mritz_mask: UploadFile = File(...),
    petpz_mask: UploadFile = File(...),
    pettz_mask: UploadFile = File(...),
):
    try:
        normalized = normalize_case_id(case_id)
        result = save_edited_masks(
            get_case_directory(normalized),
            {
                "mripz_mask.nii.gz": await mripz_mask.read(),
                "mritz_mask.nii.gz": await mritz_mask.read(),
                "petpz_mask.nii.gz": await petpz_mask.read(),
                "pettz_mask.nii.gz": await pettz_mask.read(),
            },
        )
        return {"case_id": normalized, **result}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"保存阅片器掩膜失败：{error}") from error

@router.post("/cases/prepare", response_model=PreparedCaseResponse)
def prepare_case(
    mri_zip: UploadFile = File(...),
    psma_zip: UploadFile = File(...),
    start_mri: int = Form(...),
    end_mri: int = Form(...),
    start_ct: int = Form(...),
    end_ct: int = Form(...),
    patient_name: str = Form(...),
    age: int = Form(...),
    psa: float = Form(...),
    ft_psa: float = Form(...),
    case_id: str | None = Form(None),
):
    try:
        return prepare_case_data(
            mri_zip,
            psma_zip,
            start_mri,
            end_mri,
            start_ct,
            end_ct,
            patient_name,
            age,
            psa,
            ft_psa,
            case_id,
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ValueError, zipfile.BadZipFile) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"数据准备失败：{error}") from error

