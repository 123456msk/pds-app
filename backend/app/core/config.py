"""Central filesystem configuration."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CASES_DIR = DATA_DIR / "cases"
STAGING_DIR = DATA_DIR / ".staging"
SEGMENTATION_MODEL_DIR = BASE_DIR / "app" / "models" / "segmentation"
SEGMENTATION_UTILS_DIR = SEGMENTATION_MODEL_DIR / "Utils"
SEGMENTATION_NNUNET_DIR = SEGMENTATION_MODEL_DIR / "nnUnet_paths"

for directory in (CASES_DIR, STAGING_DIR):
    directory.mkdir(parents=True, exist_ok=True)