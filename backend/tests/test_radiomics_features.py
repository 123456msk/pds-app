import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.radiomics_features import extract_pz_tz_features


class RadiomicsFeatureTests(unittest.TestCase):
    def test_extract_pz_tz_features_uses_pet_image_and_masks(self):
        calls = []

        class FakeExtractor:
            def __init__(self, params_path):
                self.params_path = params_path

            def execute(self, image_path, mask_path):
                calls.append((Path(image_path).name, Path(mask_path).name))
                return {"original_firstorder_Mean": 1.0}

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            params_path = directory / "params.yaml"
            for filename in ("pet.nii.gz", "petpz_mask.nii.gz", "pettz_mask.nii.gz", "params.yaml"):
                (directory / filename).write_bytes(b"placeholder")

            with patch("app.services.radiomics_features.featureextractor.RadiomicsFeatureExtractor", FakeExtractor):
                features, details = extract_pz_tz_features(directory, params_path)

        self.assertEqual(
            calls,
            [
                ("pet.nii.gz", "petpz_mask.nii.gz"),
                ("pet.nii.gz", "pettz_mask.nii.gz"),
            ],
        )
        self.assertEqual(details["image"], str(directory / "pet.nii.gz"))
        self.assertIn("PZ_original_firstorder_Mean", features)
        self.assertIn("TZ_original_firstorder_Mean", features)


if __name__ == "__main__":
    unittest.main()
