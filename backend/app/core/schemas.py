"""Pydantic response schemas shared by API routers."""

from pydantic import BaseModel


class VolumeInfo(BaseModel):
    modality: str
    series_uid: str
    series_description: str
    source_count: int
    selected_count: int
    selected_indices: list[int]
    ordered_indices: list[int | None]
    ordered_filenames: list[str]
    range_selected_indices: list[int]
    dicom_directory: str


class PreparedCaseResponse(BaseModel):
    success: bool
    case_id: str
    case_directory: str
    manifest_path: str
    patient: dict
    ranges: dict
    volumes: dict[str, VolumeInfo]


class SegmentationResponse(BaseModel):
    success: bool
    case_id: str
    segmentation: dict
