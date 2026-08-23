import unittest

from bridge_demo import add


class TestAdd(unittest.TestCase):
    """Tests for the bridge_demo.add function."""

    def test_integers(self) -> None:
        self.assertEqual(add(2, 3), 5)

    def test_negative_numbers(self) -> None:
        self.assertEqual(add(-4, -6), -10)

    def test_floating_point_numbers(self) -> None:
        self.assertAlmostEqual(add(1.25, 2.5), 3.75)


if __name__ == "__main__":
    unittest.main()
