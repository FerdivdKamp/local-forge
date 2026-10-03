import unittest

from cart import total


class HiddenTests(unittest.TestCase):
    def test_quantities(self):
        self.assertEqual(total([(3, 2), (2.5, 4)]), 16)

    def test_discount_and_empty(self):
        self.assertEqual(total([(19.99, 2)], 25), 29.98)
        self.assertEqual(total([], 10), 0)


if __name__ == "__main__":
    unittest.main()
