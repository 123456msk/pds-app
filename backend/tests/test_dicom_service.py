import tempfile
import unittest
from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from app.services.dicom_processing import (
    DicomRecord,
    SelectedSeries,
    convert_to_nifti,
    materialize_series,
    parse_leading_index,
    prepare_volume,
    validate_closed_range,
)
from app.core.storage import normalize_case_id
from app.services.case_preparation import calculate_pet_range


class DicomServiceTests(unittest.TestCase):
    def test_parse_leading_index(self):
        self.assertEqual(parse_leading_index("1_0"), 1)
        self.assertEqual(parse_leading_index("563_2.dcm"), 563)
        self.assertEqual(parse_leading_index("folder/17_1.ima"), 17)
        self.assertIsNone(parse_leading_index("IM_0015.dcm"))

    def test_closed_range_validation(self):
        validate_closed_range(4, 17, "MRI")
        with self.assertRaises(ValueError):
            validate_closed_range(17, 4, "MRI")

    def test_ct_range_maps_to_pet_by_total_slice_ratio(self):
        result = calculate_pet_range(2, 4, 50, 100)
        self.assertEqual(result["start"], 4)
        self.assertEqual(result["end"], 8)
        self.assertEqual(result["ratio"], 2.0)

    def test_case_id_validation(self):
        self.assertEqual(normalize_case_id("case-001"), "case-001")
        with self.assertRaises(ValueError):
            normalize_case_id("../case")

    def test_materialize_and_convert_series_to_nifti(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            series_uid = generate_uid()
            records = []
            for index, z_position in enumerate((0.0, 2.5, 5.0), start=4):
                dicom_path = root / f"{index}_0.dcm"
                self._write_test_dicom(
                    dicom_path,
                    series_uid=series_uid,
                    instance_number=index,
                    z_position=z_position,
                    pixel_value=index,
                )
                records.append(
                    DicomRecord(
                        archive_path=dicom_path.name,
                        extracted_path=dicom_path,
                        series_uid=series_uid,
                        series_description="T2 AX",
                        modality="MR",
                        file_index=index,
                        instance_number=index,
                        position=(0.0, 0.0, z_position),
                        orientation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                    )
                )

            series = SelectedSeries(
                uid=series_uid,
                description="T2 AX",
                modality="MR",
                all_records=records,
                selected_records=records,
            )
            dicom_paths = materialize_series(series, root / "case" / "dicom" / "mri")
            self.assertEqual([path.name for path in dicom_paths], ["4_0.dcm", "5_0.dcm", "6_0.dcm"])
            output_path = root / "case" / "nifti" / "mri.nii.gz"
            convert_to_nifti(dicom_paths, output_path)

            image = sitk.ReadImage(str(output_path))
            array = sitk.GetArrayFromImage(image)
            self.assertEqual(array.shape, (3, 4, 5))
            for actual, expected in zip(image.GetSpacing(), (0.8, 0.7, 2.5)):
                self.assertAlmostEqual(actual, expected, places=5)
            self.assertEqual(int(array[0, 0, 0]), 4)
            self.assertEqual(int(array[2, 0, 0]), 6)

    def test_prepare_volume_keeps_full_series_before_final_crop(self):
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            series_uid = generate_uid()
            records = []
            for index in range(1, 7):
                path = root / f"{index}_0.dcm"
                self._write_test_dicom(
                    path,
                    series_uid=series_uid,
                    instance_number=index,
                    z_position=float(index),
                    pixel_value=index,
                )
                records.append(
                    DicomRecord(
                        archive_path=path.name,
                        extracted_path=path,
                        series_uid=series_uid,
                        series_description="T2 AX",
                        modality="MR",
                        file_index=index,
                        instance_number=index,
                        position=(0.0, 0.0, float(index)),
                        orientation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                    )
                )

            volume = prepare_volume(
                records,
                lambda record: record.modality == "MR",
                2,
                4,
                "T2W MRI",
                "mri",
                root / "case",
            )
            self.assertEqual(len(volume["ordered_filenames"]), 6)
            self.assertEqual(volume["range_selected_indices"], [2, 3, 4])

    @staticmethod
    def _write_test_dicom(
        path: Path,
        series_uid: str,
        instance_number: int,
        z_position: float,
        pixel_value: int,
    ):
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = pydicom.uid.MRImageStorage
        file_meta.MediaStorageSOPInstanceUID = generate_uid()
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        file_meta.ImplementationClassUID = generate_uid()

        data_set = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
        data_set.SOPClassUID = file_meta.MediaStorageSOPClassUID
        data_set.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
        data_set.StudyInstanceUID = generate_uid()
        data_set.SeriesInstanceUID = series_uid
        data_set.FrameOfReferenceUID = generate_uid()
        data_set.Modality = "MR"
        data_set.SeriesDescription = "T2 AX"
        data_set.InstanceNumber = instance_number
        data_set.ImagePositionPatient = [0.0, 0.0, z_position]
        data_set.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        data_set.PixelSpacing = [0.7, 0.8]
        data_set.SliceThickness = 2.5
        data_set.Rows = 4
        data_set.Columns = 5
        data_set.SamplesPerPixel = 1
        data_set.PhotometricInterpretation = "MONOCHROME2"
        data_set.BitsAllocated = 16
        data_set.BitsStored = 16
        data_set.HighBit = 15
        data_set.PixelRepresentation = 1
        pixels = np.full((4, 5), pixel_value, dtype=np.int16)
        data_set.PixelData = pixels.tobytes()
        data_set.save_as(path, enforce_file_format=True)


if __name__ == "__main__":
    unittest.main()
