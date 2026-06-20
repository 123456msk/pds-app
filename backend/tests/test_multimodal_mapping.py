import unittest

import numpy as np

from app.services.multimodal_mapping import _distribute, _similarity_transform


class MultimodalMappingTests(unittest.TestCase):
    def test_distribute_maps_every_target_slice_once(self):
        mapping = _distribute(3, 8)
        targets = [target for values in mapping.values() for target in values]
        self.assertEqual(targets, list(range(8)))

    def test_similarity_transform_maps_two_landmarks(self):
        transform = _similarity_transform(((0, 0), (10, 0)), ((5, 7), (25, 7)))
        points = np.array([[0, 0, 1], [10, 0, 1]], dtype=np.float32)
        mapped = points @ transform.T
        np.testing.assert_allclose(mapped, np.array([[5, 7], [25, 7]]), atol=1e-5)


if __name__ == "__main__":
    unittest.main()