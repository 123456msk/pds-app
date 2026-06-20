import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from app.services.result_edits import EDITABLE_MASKS, save_edited_masks


class ResultEditTests(unittest.TestCase):
    def test_save_edited_masks_replaces_four_masks_and_rebuilds_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_directory = Path(temporary)
            results = case_directory / "results"
            results.mkdir()
            image = sitk.GetImageFromArray(np.zeros((3, 4, 5), dtype=np.int16))
            for image_name in {"mri.nii.gz", "pet.nii.gz"}:
                sitk.WriteImage(image, str(results / image_name), True)
            payloads = {}
            for filename in EDITABLE_MASKS:
                original = sitk.GetImageFromArray(np.zeros((3, 4, 5), dtype=np.uint8))
                sitk.WriteImage(original, str(results / filename), True)
                edited = sitk.GetImageFromArray(np.ones((3, 4, 5), dtype=np.uint8))
                candidate = case_directory / ("edited_" + filename)
                sitk.WriteImage(edited, str(candidate), True)
                payloads[filename] = candidate.read_bytes()
            (case_directory / "manifest.json").write_text(json.dumps({"case_id": "test"}), encoding="utf-8")

            result = save_edited_masks(case_directory, payloads)

            self.assertEqual(set(result["files"]), set(EDITABLE_MASKS))
            for filename in EDITABLE_MASKS:
                saved = sitk.GetArrayFromImage(sitk.ReadImage(str(results / filename)))
                self.assertTrue(np.all(saved == 1))
            with zipfile.ZipFile(case_directory / "results.zip") as archive:
                self.assertTrue(set(EDITABLE_MASKS).issubset(archive.namelist()))
            manifest = json.loads((case_directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["viewer_edits"]["files"]), set(EDITABLE_MASKS))


if __name__ == "__main__":
    unittest.main()
