import tempfile
import unittest
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from app.services.prediction_input import merge_prediction_features
from app.services.clinical_features import (
    build_clinical_features,
    calculate_high_pet_volume,
    calculate_mask_volume,
    compute_zone_volumes,
)


def write_image(path: Path, array: np.ndarray, spacing=(1.0, 1.0, 1.0)):
    image = sitk.GetImageFromArray(array)
    image.SetSpacing(spacing)
    sitk.WriteImage(image, str(path), True)


class ClinicalFeatureTests(unittest.TestCase):
    def test_mask_volume_and_zone_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mask.nii.gz"
            array = np.zeros((2, 3, 4), dtype=np.uint8)
            array.flat[:10] = 1
            write_image(path, array, spacing=(2.0, 2.0, 2.0))
            result = calculate_mask_volume(path)
            self.assertAlmostEqual(result["volume_ml"], 0.08)
            zones = compute_zone_volumes(
                {"volume_ml": 30.0}, {"volume_ml": 10.0}, {"volume_ml": 0.5}
            )
            self.assertEqual(zones["pzv_method"], "WG-TZ")
            self.assertAlmostEqual(zones["pzv"], 20.0)
            self.assertAlmostEqual(zones["pzratio"], 2 / 3)

    def test_high_pet_volume_uses_masked_95th_percentile(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            pet = np.arange(100, dtype=np.float32).reshape(4, 5, 5)
            mask = np.ones_like(pet, dtype=np.uint8)
            write_image(directory / "pet.nii.gz", pet)
            write_image(directory / "petwg_mask.nii.gz", mask)
            result = calculate_high_pet_volume(directory / "pet.nii.gz", directory / "petwg_mask.nii.gz")
            self.assertEqual(result["high_voxels"], 5)
            self.assertAlmostEqual(result["high_volume_ml"], 0.005)

    def test_merge_order_matches_radiomics_then_json_features(self):
        radiomics = {"PZ_feature": 1.0, "TZ_feature": 2.0}
        clinical = {
            "age": 65.0, "PSA": 8.5, "f_tPSA": 0.16, "volume_ml": 40.0,
            "high_volume_ml": 1.0, "psad": 0.2125, "tzv": 20.0,
            "pzv": 18.0, "pzratio": 0.45,
        }
        merged = merge_prediction_features(radiomics, clinical)
        self.assertEqual(list(merged)[:2], ["PZ_feature", "TZ_feature"])
        self.assertNotIn("volume_ml", merged)
        self.assertEqual(list(merged)[-8:], [name for name in clinical if name != "volume_ml"])
    def test_final_clinical_feature_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shape = (10, 10, 10)
            wg = np.ones(shape, dtype=np.uint8)
            tz = np.zeros(shape, dtype=np.uint8); tz.flat[:400] = 1
            pz = np.zeros(shape, dtype=np.uint8); pz.flat[400:1000] = 1
            pet = np.arange(1000, dtype=np.float32).reshape(shape)
            for name, array in {
                "mriwg_mask.nii.gz": wg,
                "mritz_mask.nii.gz": tz,
                "mripz_mask.nii.gz": pz,
                "petwg_mask.nii.gz": wg,
                "pet.nii.gz": pet,
            }.items():
                write_image(directory / name, array, spacing=(2.0, 2.0, 2.0))
            features, _ = build_clinical_features(
                {"age": 65, "psa": 8.5, "ft_psa": 0.16}, directory
            )
            self.assertEqual(
                list(features),
                ["age", "PSA", "f_tPSA", "volume_ml", "high_volume_ml", "psad", "tzv", "pzv", "pzratio"],
            )
            self.assertAlmostEqual(features["volume_ml"], 8.0)
            self.assertAlmostEqual(features["psad"], 8.5 / 8.0)


if __name__ == "__main__":
    unittest.main()


