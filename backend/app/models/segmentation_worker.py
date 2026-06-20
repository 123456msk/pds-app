"""Execute the copied MRI segmentation project without modifying it."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def _reset_directory(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def _resolve(model_directory: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else model_directory / path


def run(model_directory: Path, case_directory: Path, case_id: str) -> dict:
    model_directory = model_directory.resolve()
    case_directory = case_directory.resolve()
    os.chdir(model_directory)
    sys.path.insert(0, str(model_directory))
    sys.dont_write_bytecode = True
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    import torch
    original_torch_load = torch.load
    def compatible_torch_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_torch_load(*args, **kwargs)
    torch.load = compatible_torch_load

    from Utils import InputCheck, helpers, segmentor_pipeline
    from Utils.get_images import get_images

    patients_directory = model_directory / "Pats"
    outputs_directory = model_directory / "Outputs"
    input_directory = patients_directory / case_id
    _reset_directory(patients_directory)
    _reset_directory(outputs_directory)
    input_directory.mkdir(parents=True, exist_ok=True)
    nnunet_raw = model_directory / "nnUnet_paths" / "nnUNet_raw"
    for relative in (
        "Dataset016_WgSegmentationPNetAndPicai/ImagesTs",
        "Dataset019_ProstateZonesSegmentationWgFilteredLessDilated/ImagesTs",
        "OutcomesWG",
        "OutcomesZones",
    ):
        (nnunet_raw / relative).mkdir(parents=True, exist_ok=True)

    source_directory = case_directory / "dicom" / "mri"
    source_files = [path for path in source_directory.iterdir() if path.is_file()]
    for source in source_files:
        shutil.copy2(source, input_directory / source.name)

    patient_list = get_images(str(Path("Pats") / case_id))
    if len(patient_list) != 1:
        raise RuntimeError(f"模型要求一个 T2 MRI 体数据，实际得到 {len(patient_list)} 个。")

    source_nifti = _resolve(model_directory, patient_list[0])
    patients = InputCheck.load_nii_gz_files(patient_list)
    segmentor_pipeline.segmentor_pipeline_operation(output_volume="Outputs", pats=patients)
    helpers.process_masks(out_volume="Outputs")

    output_index = json.loads((outputs_directory / "ResampledToOriginalSegmentationPaths.json").read_text(encoding="utf-8"))
    if len(output_index) != 1:
        raise RuntimeError("分割结果索引数量异常。")
    result_paths = next(iter(output_index.values()))

    segmentation_directory = case_directory / "segmentation" / "results"
    segmentation_directory.mkdir(parents=True, exist_ok=True)
    output_files = {
        "wg": segmentation_directory / "mriwg_mask.nii.gz",
        "pz": segmentation_directory / "mripz_mask.nii.gz",
        "tz": segmentation_directory / "mritz_mask.nii.gz",
    }
    for zone, key in (("wg", "wg_binary"), ("pz", "pz_binary"), ("tz", "tz_binary")):
        shutil.copy2(_resolve(model_directory, result_paths[key]), output_files[zone])

    nifti_directory = case_directory / "nifti"
    nifti_directory.mkdir(parents=True, exist_ok=True)
    full_mri_path = nifti_directory / "mri_full.nii.gz"
    shutil.copy2(source_nifti, full_mri_path)

    summary = {
        "input_slice_count": len(source_files),
        "mri_nifti": str(full_mri_path),
        "masks": {zone: str(path) for zone, path in output_files.items()},
    }
    (case_directory / "segmentation" / "worker_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _reset_directory(patients_directory)
    _reset_directory(outputs_directory)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    arguments = parser.parse_args()
    run(arguments.model_dir, arguments.case_dir, arguments.case_id)


if __name__ == "__main__":
    main()