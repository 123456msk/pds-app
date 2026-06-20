"""DICOM extraction, full-series selection, and spatially ordered NIfTI conversion."""

import re
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

import pydicom
import SimpleITK as sitk
from SimpleITK import ImageSeriesReader_GetGDCMSeriesFileNames


DICOM_SUFFIXES = {".dcm", ".ima"}
LEADING_INDEX_PATTERN = re.compile(r"^(\d+)")


@dataclass(frozen=True)
class DicomRecord:
    archive_path: str
    extracted_path: Path
    series_uid: str
    series_description: str
    modality: str
    file_index: int | None
    instance_number: int
    position: tuple[float, float, float] | None
    orientation: tuple[float, float, float, float, float, float] | None


@dataclass(frozen=True)
class SelectedSeries:
    uid: str
    description: str
    modality: str
    all_records: list[DicomRecord]
    selected_records: list[DicomRecord]


def parse_leading_index(filename: str) -> int | None:
    match = LEADING_INDEX_PATTERN.match(Path(filename).name)
    return int(match.group(1)) if match else None


def validate_closed_range(start: int, end: int, label: str) -> None:
    if start < 0 or end < 0:
        raise ValueError(f"{label} 范围不能为负数。")
    if start > end:
        raise ValueError(f"{label} 起始序号不能大于结束序号。")


def _looks_like_dicom(path: str) -> bool:
    name = PurePosixPath(path).name
    return (
        PurePosixPath(name).suffix.lower() in DICOM_SUFFIXES
        or bool(re.fullmatch(r"\d+_\d+", name))
    )


def _safe_archive_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"ZIP 包含不安全路径：{name}")
    return path


def extract_dicom_zip(zip_path: Path, destination: Path) -> list[DicomRecord]:
    destination.mkdir(parents=True, exist_ok=True)
    records: list[DicomRecord] = []
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or member.filename.startswith("__MACOSX"):
                continue
            archive_path = _safe_archive_path(member.filename)
            if not _looks_like_dicom(str(archive_path)):
                continue
            extracted_path = destination / f"{len(records):06d}_{archive_path.name}"
            with archive.open(member) as source, extracted_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            try:
                data_set = pydicom.dcmread(
                    extracted_path, stop_before_pixels=True, force=True
                )
                position_value = getattr(data_set, "ImagePositionPatient", None)
                orientation_value = getattr(data_set, "ImageOrientationPatient", None)
                records.append(
                    DicomRecord(
                        archive_path=str(archive_path),
                        extracted_path=extracted_path,
                        series_uid=str(getattr(data_set, "SeriesInstanceUID", "unknown")),
                        series_description=str(getattr(data_set, "SeriesDescription", "")),
                        modality=str(getattr(data_set, "Modality", "")).upper(),
                        file_index=parse_leading_index(archive_path.name),
                        instance_number=int(getattr(data_set, "InstanceNumber", 0) or 0),
                        position=(
                            tuple(float(value) for value in position_value)
                            if position_value is not None and len(position_value) == 3
                            else None
                        ),
                        orientation=(
                            tuple(float(value) for value in orientation_value)
                            if orientation_value is not None and len(orientation_value) == 6
                            else None
                        ),
                    )
                )
            except Exception:
                extracted_path.unlink(missing_ok=True)
    if not records:
        raise ValueError(f"{zip_path.name} 中没有找到可解析的 DICOM 文件。")
    return records


def _series_text(record: DicomRecord) -> str:
    data_set = pydicom.dcmread(
        record.extracted_path, stop_before_pixels=True, force=True
    )
    return " ".join(
        str(getattr(data_set, field, ""))
        for field in ("SeriesDescription", "ProtocolName", "SequenceName", "ImageType")
    ).lower()


def is_t2_mri(record: DicomRecord) -> bool:
    text = _series_text(record)
    return (
        record.modality == "MR"
        and ("t2" in text or "tse" in text)
        and "sag" not in text
        and "cor" not in text
    )


def is_ct(record: DicomRecord) -> bool:
    return record.modality == "CT"


def is_pet(record: DicomRecord) -> bool:
    return record.modality in {"PT", "PET"}


def select_series(
    records: list[DicomRecord],
    predicate: Callable[[DicomRecord], bool],
    label: str,
) -> SelectedSeries:
    groups: dict[str, list[DicomRecord]] = defaultdict(list)
    for record in records:
        if predicate(record):
            groups[record.series_uid].append(record)
    if not groups:
        raise ValueError(f"没有识别到 {label} 序列。")
    uid, all_records = max(groups.items(), key=lambda item: len(item[1]))
    first = all_records[0]
    return SelectedSeries(
        uid=uid,
        description=first.series_description,
        modality=first.modality,
        all_records=all_records,
        selected_records=all_records,
    )


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def sort_records(records: list[DicomRecord]) -> list[DicomRecord]:
    reference = next(
        (
            record
            for record in records
            if record.position is not None and record.orientation is not None
        ),
        None,
    )
    if reference:
        normal = _cross(reference.orientation[:3], reference.orientation[3:])
        return sorted(
            records,
            key=lambda record: (
                _dot(record.position, normal)
                if record.position is not None
                else float(record.instance_number),
                record.file_index if record.file_index is not None else record.instance_number,
            ),
        )
    return sorted(
        records,
        key=lambda record: (
            record.instance_number,
            record.file_index if record.file_index is not None else 0,
        ),
    )


def materialize_series(series: SelectedSeries, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    output_paths = []
    for order, record in enumerate(sort_records(series.all_records)):
        output_path = destination / Path(record.archive_path).name
        if output_path.exists():
            output_path = destination / f"{output_path.stem}__{order}{output_path.suffix}"
        shutil.copy2(record.extracted_path, output_path)
        output_paths.append(output_path)
    return output_paths


def spatially_ordered_paths(directory: Path) -> list[Path]:
    return [
        Path(path)
        for path in ImageSeriesReader_GetGDCMSeriesFileNames(str(directory))
    ]


def convert_to_nifti(dicom_paths: list[Path], output_path: Path) -> None:
    if not dicom_paths:
        raise ValueError("没有可转换的 DICOM 文件。")
    if len(dicom_paths) <= 1:
        raise ValueError("DICOM 序列至少需要两个切片，不支持单文件多帧序列。")
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames([str(path) for path in dicom_paths])
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    image = reader.Execute()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(image, str(output_path), True)


def prepare_volume(
    records: list[DicomRecord],
    predicate: Callable[[DicomRecord], bool],
    start: int,
    end: int,
    label: str,
    modality_key: str,
    case_directory: Path,
) -> dict:
    series = select_series(records, predicate, label)
    requested_records = [
        record
        for record in series.all_records
        if record.file_index is not None and start <= record.file_index <= end
    ]
    if not requested_records and modality_key != "pet":
        raise ValueError(f"{label} 在闭区间 [{start}, {end}] 内没有匹配文件。")

    dicom_directory = case_directory / "dicom" / modality_key
    dicom_paths = materialize_series(series, dicom_directory)
    ordered_paths = spatially_ordered_paths(dicom_directory)
    if len(ordered_paths) <= 1:
        raise ValueError(f"{label} 序列至少需要两个切片。")
    record_by_name = {
        path.name: record
        for path, record in zip(dicom_paths, sort_records(series.all_records))
    }
    ordered_indices = [record_by_name[path.name].file_index for path in ordered_paths]
    requested_indices = [
        index
        for index in ordered_indices
        if index is not None and start <= index <= end
    ]
    return {
        "modality": series.modality,
        "series_uid": series.uid,
        "series_description": series.description,
        "source_count": len(series.all_records),
        "selected_count": len(series.all_records),
        "selected_indices": [index for index in ordered_indices if index is not None],
        "ordered_indices": ordered_indices,
        "ordered_filenames": [path.name for path in ordered_paths],
        "range_selected_indices": requested_indices,
        "dicom_directory": str(Path("dicom") / modality_key),
    }
