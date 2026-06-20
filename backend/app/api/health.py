"""Health endpoint for storage and segmentation assets."""

from fastapi import APIRouter

from app.core.config import CASES_DIR, SEGMENTATION_NNUNET_DIR, SEGMENTATION_UTILS_DIR

router = APIRouter(tags=["health"])


def _checkpoint(dataset: str):
    return SEGMENTATION_NNUNET_DIR / "nnUNet_results" / dataset / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0" / "checkpoint_final.pth"


@router.get("/health")
def health():
    return {
        "status": "ok",
        "cases_directory": str(CASES_DIR),
        "models": {
            "utils": SEGMENTATION_UTILS_DIR.exists(),
            "whole_gland": _checkpoint("Dataset016_WgSegmentationPNetAndPicai").exists(),
            "zones": _checkpoint("Dataset019_ProstateZonesSegmentationWgFilteredLessDilated").exists(),
        },
    }