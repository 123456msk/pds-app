# PDS FastAPI backend

## Pipeline

1. `POST /api/cases/prepare` receives every selected MRI and PSMA PET/CT DICOM.
2. The backend identifies and stores complete T2W MRI, CT, and PET series.
3. `POST /api/cases/{case_id}/segment` sends the complete T2W MRI series through the copied original nnU-Net pipeline.
4. The original pipeline creates whole-gland (WG), peripheral-zone (PZ), and transition-zone (TZ) masks in original MRI space.
5. The saved MRI and CT closed ranges crop the output volumes. PET range is calculated from the CT/PET total-slice ratio.
6. Femoral-head detection from `app/algorithms/multimodal` aligns MRI masks to CT. CT masks are mapped to PET using DICOM physical positions and pixel spacing.
7. The case `results` directory and `results.zip` contain exactly 12 files:

```text
mri.nii.gz        mriwg_mask.nii.gz  mripz_mask.nii.gz  mritz_mask.nii.gz
ct.nii.gz         ctwg_mask.nii.gz   ctpz_mask.nii.gz   cttz_mask.nii.gz
pet.nii.gz        petwg_mask.nii.gz  petpz_mask.nii.gz  pettz_mask.nii.gz
```

## Local model assets

- `app/models/segmentation/Utils`: unchanged copy of the original model utilities.
- `app/models/segmentation/nnUnet_paths`: nnU-Net plans and WG/PZ/TZ checkpoints.
- `app/algorithms/multimodal/ct_utils.py`: unchanged CT femoral-head detector.
- `app/algorithms/multimodal/mri_utils.py`: unchanged MRI femoral-head detector.
- `app/models/segmentation_worker.py`: backend adapter around the copied model.
- `app/services/multimodal_mapping.py`: range cropping and MRI→CT→PET output generation.

## API

- `GET /api/health`
- `POST /api/cases/prepare`
- `GET /api/cases/{case_id}`
- `POST /api/cases/{case_id}/segment`
- `GET /api/cases/{case_id}/results`

## Start

```powershell
cd D:\1Item\PDS\pds-backend\pds-app\backend
.\.venv\python.exe -X utf8 run.py
```