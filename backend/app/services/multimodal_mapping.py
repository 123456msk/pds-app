"""Crop segmented MRI and map WG/PZ/TZ masks to CT and PET."""

import json
import math
import shutil
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pydicom
import SimpleITK as sitk

from app.algorithms.multimodal.ct_utils import find_femoral_heads_adaptive
from app.algorithms.multimodal.mri_utils import load_dicom, find_femoral_heads_from_mask

MRI_CONFIG = {
    "CENTER_BAND_RATIO": 0.3,
    "MIN_AREA": 1500,
    "ERODE_ITERATIONS": 1,
    "FEMORAL_HEAD_DIAMETER_MM_RANGE": (35, 60),
    "PIXEL_SPACING_FALLBACK": (0.7, 0.7),
    "VERTICAL_CROP": (0.3, 0.6),
    "HORIZONTAL_CROP": (0.25, 0.75),
}
CT_CONFIG = {
    "FEMORAL_HEAD_DIAMETER_MM_RANGE": (40, 55),
    "DEFAULT_PIXEL_SPACING": 0.976,
    "MIN_CT_SLICE_INDEX": 300,
    "BONE_THRESHOLD_HU": 220,
    "MIN_BONE_AREA_PIXELS": 500,
    "MORPH_KERNEL_SIZE": (7, 7),
    "MORPH_ITERATIONS": 3,
    "SOFT_TISSUE_WINDOW": (50, 400),
    "BONE_WINDOW_HOUGH": (400, 1800),
    "HOUGH_CIRCLES_PARAMS": {"dp": 1, "minDist": 1, "param1": 80, "param2": 20},
}

ZONE_FILES = {
    "wg": "mriwg_mask.nii.gz",
    "pz": "mripz_mask.nii.gz",
    "tz": "mritz_mask.nii.gz",
}
EXPECTED_NAMES = {
    "mri.nii.gz", "mriwg_mask.nii.gz", "mripz_mask.nii.gz", "mritz_mask.nii.gz",
    "ct.nii.gz", "ctwg_mask.nii.gz", "ctpz_mask.nii.gz", "cttz_mask.nii.gz",
    "pet.nii.gz", "petwg_mask.nii.gz", "petpz_mask.nii.gz", "pettz_mask.nii.gz",
}


def _load_manifest(case_directory: Path) -> dict:
    return json.loads((case_directory / "manifest.json").read_text(encoding="utf-8"))


def _ordered_paths(case_directory: Path, volume: dict) -> list[Path]:
    directory = case_directory / volume["dicom_directory"]
    paths = [directory / name for name in volume["ordered_filenames"]]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"DICOM 文件缺失：{missing[:3]}")
    return paths


def _positions_by_file_index(volume: dict, start: int, end: int) -> list[int]:
    positions = [
        position for position, index in enumerate(volume["ordered_indices"])
        if index is not None and start <= index <= end
    ]
    if not positions:
        raise ValueError(f"闭区间 [{start}, {end}] 内没有匹配 DICOM。")
    return positions


def _positions_by_ordinal(volume: dict, start: int, end: int) -> list[int]:
    count = len(volume["ordered_filenames"])
    first = max(1, start)
    last = min(count, end)
    if first > last:
        raise ValueError(f"位置区间 [{start}, {end}] 超出序列张数 {count}。")
    return list(range(first - 1, last))


def _read_dicom_volume(paths: list[Path]) -> sitk.Image:
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames([str(path) for path in paths])
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    return reader.Execute()


def _extract_slices(image: sitk.Image, positions: list[int]) -> sitk.Image:
    if not positions:
        raise ValueError("裁剪切片为空。")
    if positions == list(range(positions[0], positions[-1] + 1)):
        size = list(image.GetSize())
        size[2] = len(positions)
        return sitk.Extract(image, size, [0, 0, positions[0]])
    array = sitk.GetArrayFromImage(image)[positions]
    output = sitk.GetImageFromArray(array)
    output.SetSpacing(image.GetSpacing())
    output.SetDirection(image.GetDirection())
    output.SetOrigin(image.TransformIndexToPhysicalPoint((0, 0, positions[0])))
    return output


def _representative_center(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    values = np.asarray(points, dtype=np.float32)
    if len(values) == 1:
        return tuple(map(float, values[0]))
    span = values.max(axis=0) - values.min(axis=0)
    radius = max(25.0, float(np.linalg.norm(span)) * 0.10)
    distances = np.linalg.norm(values[:, None, :] - values[None, :, :], axis=-1)
    best = int((distances <= radius).sum(axis=1).argmax())
    cluster = values[distances[best] <= radius]
    centroid = cluster.mean(axis=0)
    nearest = int(np.linalg.norm(values - centroid, axis=1).argmin())
    return tuple(map(float, values[nearest]))


def _detect_mri_centers(paths: list[Path]):
    left, right = [], []
    for path in paths:
        array, _ = load_dicom(str(path))
        if array is None:
            continue
        detections, _ = find_femoral_heads_from_mask(array, MRI_CONFIG)
        for result in detections or []:
            center = result.get("center")
            side = result.get("side", "").lower()
            if center is not None and side == "left":
                left.append(center)
            elif center is not None and side == "right":
                right.append(center)
    centers = (_representative_center(left), _representative_center(right))
    if centers[0] is None or centers[1] is None:
        raise RuntimeError("MRI 范围内未能稳定检测到双侧股骨头中心。")
    return centers


def _detect_ct_centers(paths: list[Path]):
    left, right = [], []
    for path in paths:
        detections, _ = find_femoral_heads_adaptive(str(path), CT_CONFIG)
        for result in detections or []:
            center = result.get("center")
            side = result.get("side", "")
            if center is not None and side == "左侧":
                left.append(center)
            elif center is not None and side == "右侧":
                right.append(center)
    centers = (_representative_center(left), _representative_center(right))
    if centers[0] is None or centers[1] is None:
        raise RuntimeError("CT 范围内未能稳定检测到双侧股骨头中心。")
    return centers


def _similarity_transform(mri_centers, ct_centers) -> np.ndarray:
    vector_mri = np.subtract(mri_centers[1], mri_centers[0]).astype(np.float64)
    vector_ct = np.subtract(ct_centers[1], ct_centers[0]).astype(np.float64)
    length_mri = np.linalg.norm(vector_mri)
    length_ct = np.linalg.norm(vector_ct)
    if length_mri < 1e-6 or length_ct < 1e-6:
        raise RuntimeError("股骨头中心点重合，无法计算 MRI→CT 变换。")
    scale = length_ct / length_mri
    angle = math.atan2(vector_ct[1], vector_ct[0]) - math.atan2(vector_mri[1], vector_mri[0])
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]],
        dtype=np.float64,
    )
    mri_midpoint = np.mean(np.asarray(mri_centers, dtype=np.float64), axis=0)
    ct_midpoint = np.mean(np.asarray(ct_centers, dtype=np.float64), axis=0)
    matrix = scale * rotation
    translation = ct_midpoint - matrix @ mri_midpoint
    return np.hstack([matrix, translation.reshape(2, 1)]).astype(np.float32)


def _distribute(source_count: int, target_count: int) -> dict[int, list[int]]:
    if source_count <= 0 or target_count <= 0:
        raise ValueError("映射源和目标切片数必须大于 0。")
    mapping = {index: [] for index in range(source_count)}
    for target in range(target_count):
        source = min(source_count - 1, int((target + 0.5) * source_count / target_count))
        mapping[source].append(target)
    return mapping


def _map_mri_mask_to_ct(mask: sitk.Image, mri_positions: list[int], ct_image: sitk.Image, matrix: np.ndarray) -> sitk.Image:
    source = sitk.GetArrayFromImage(mask)
    target_shape = tuple(reversed(ct_image.GetSize()))
    mapped = np.zeros(target_shape, dtype=np.uint8)
    for source_local, target_locals in _distribute(len(mri_positions), target_shape[0]).items():
        source_position = mri_positions[source_local]
        if source_position >= source.shape[0]:
            continue
        for target_local in target_locals:
            mapped[target_local] = cv2.warpAffine(
                (source[source_position] > 0).astype(np.uint8), matrix,
                (target_shape[2], target_shape[1]), flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0,
            )
    output = sitk.GetImageFromArray(mapped)
    output.CopyInformation(ct_image)
    return output


def _dicom_geometry(path: Path):
    data_set = pydicom.dcmread(path, stop_before_pixels=True, force=True)
    spacing = [float(value) for value in getattr(data_set, "PixelSpacing", [1.0, 1.0])]
    position = [float(value) for value in getattr(data_set, "ImagePositionPatient", [0.0, 0.0, 0.0])]
    return int(data_set.Rows), int(data_set.Columns), spacing[0], spacing[1], position[0], position[1]


def _map_ct_mask_to_pet(mask: sitk.Image, ct_paths: list[Path], pet_paths: list[Path], pet_image: sitk.Image) -> sitk.Image:
    source = sitk.GetArrayFromImage(mask)
    target_shape = tuple(reversed(pet_image.GetSize()))
    mapped = np.zeros(target_shape, dtype=np.uint8)
    for pet_local, pet_path in enumerate(pet_paths):
        ct_local = min(len(ct_paths) - 1, int((pet_local + 0.5) * len(ct_paths) / len(pet_paths)))
        ct_rows, ct_columns, ct_rs, ct_cs, ct_x, ct_y = _dicom_geometry(ct_paths[ct_local])
        pet_rows, pet_columns, pet_rs, pet_cs, pet_x, pet_y = _dicom_geometry(pet_path)
        ct_slice = source[ct_local]
        if ct_slice.shape != (ct_rows, ct_columns):
            ct_slice = cv2.resize(ct_slice, (ct_columns, ct_rows), interpolation=cv2.INTER_NEAREST)
        transform = np.array([
            [ct_cs / pet_cs, 0.0, (ct_x - pet_x) / pet_cs],
            [0.0, ct_rs / pet_rs, (ct_y - pet_y) / pet_rs],
        ], dtype=np.float32)
        mapped[pet_local] = cv2.warpAffine(
            (ct_slice > 0).astype(np.uint8), transform, (pet_columns, pet_rows),
            flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
    output = sitk.GetImageFromArray(mapped)
    output.CopyInformation(pet_image)
    return output


def _write(image: sitk.Image, path: Path) -> str:
    sitk.WriteImage(image, str(path), True)
    return str(path)


def build_multimodal_results(case_directory: Path) -> dict:
    manifest = _load_manifest(case_directory)
    ranges = manifest["ranges"]
    volumes = manifest["volumes"]

    mri_all = _ordered_paths(case_directory, volumes["mri"])
    ct_all = _ordered_paths(case_directory, volumes["ct"])
    pet_all = _ordered_paths(case_directory, volumes["pet"])
    mri_positions = _positions_by_file_index(volumes["mri"], ranges["mri"]["start"], ranges["mri"]["end"])
    ct_positions = _positions_by_file_index(volumes["ct"], ranges["ct"]["start"], ranges["ct"]["end"])
    pet_positions = _positions_by_ordinal(volumes["pet"], ranges["pet"]["start"], ranges["pet"]["end"])
    mri_paths = [mri_all[position] for position in mri_positions]
    ct_paths = [ct_all[position] for position in ct_positions]
    pet_paths = [pet_all[position] for position in pet_positions]

    full_mri = sitk.ReadImage(str(case_directory / "nifti" / "mri_full.nii.gz"))
    mri_image = _extract_slices(full_mri, mri_positions)
    ct_image = _read_dicom_volume(ct_paths)
    pet_image = _read_dicom_volume(pet_paths)
    mri_centers = _detect_mri_centers(mri_paths)
    ct_centers = _detect_ct_centers(ct_paths)
    mri_to_ct = _similarity_transform(mri_centers, ct_centers)

    results_directory = case_directory / "results"
    shutil.rmtree(results_directory, ignore_errors=True)
    results_directory.mkdir(parents=True, exist_ok=True)
    files = {
        "mri": _write(mri_image, results_directory / "mri.nii.gz"),
        "ct": _write(ct_image, results_directory / "ct.nii.gz"),
        "pet": _write(pet_image, results_directory / "pet.nii.gz"),
    }
    zones = {}
    segmentation_directory = case_directory / "segmentation" / "results"
    for zone, source_name in ZONE_FILES.items():
        full_mask = sitk.ReadImage(str(segmentation_directory / source_name))
        mri_mask = _extract_slices(full_mask, mri_positions)
        mri_mask.CopyInformation(mri_image)
        ct_mask = _map_mri_mask_to_ct(full_mask, mri_positions, ct_image, mri_to_ct)
        pet_mask = _map_ct_mask_to_pet(ct_mask, ct_paths, pet_paths, pet_image)
        files[f"mri_{zone}"] = _write(mri_mask, results_directory / f"mri{zone}_mask.nii.gz")
        files[f"ct_{zone}"] = _write(ct_mask, results_directory / f"ct{zone}_mask.nii.gz")
        files[f"pet_{zone}"] = _write(pet_mask, results_directory / f"pet{zone}_mask.nii.gz")
        zones[zone] = {
            "mri_voxels": int(np.count_nonzero(sitk.GetArrayViewFromImage(mri_mask))),
            "ct_voxels": int(np.count_nonzero(sitk.GetArrayViewFromImage(ct_mask))),
            "pet_voxels": int(np.count_nonzero(sitk.GetArrayViewFromImage(pet_mask))),
        }

    actual_names = {path.name for path in results_directory.iterdir() if path.is_file()}
    if actual_names != EXPECTED_NAMES:
        raise RuntimeError(f"最终结果文件不完整：{sorted(EXPECTED_NAMES - actual_names)}")
    for zone, counts in zones.items():
        if not all(counts.values()):
            raise RuntimeError(f"{zone.upper()} 映射结果存在空掩膜：{counts}")

    archive_path = case_directory / "results.zip"
    archive_path.unlink(missing_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result_path in sorted(results_directory.iterdir()):
            archive.write(result_path, arcname=result_path.name)

    summary = {
        "results_directory": str(results_directory),
        "archive_path": str(archive_path),
        "file_count": len(actual_names),
        "files": files,
        "ranges": ranges,
        "slice_counts": {"mri": len(mri_paths), "ct": len(ct_paths), "pet": len(pet_paths)},
        "femoral_centers": {"mri": mri_centers, "ct": ct_centers},
        "mri_to_ct_transform": mri_to_ct.tolist(),
        "zones": zones,
    }
    (case_directory / "multimodal_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary