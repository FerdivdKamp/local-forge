import unittest

from cart import total


class CartTests(unittest.TestCase):
    def test_one_item(self):
        self.assertEqual(total([(10, 1)]), 10)


if __name__ == "__main__":
    unittest.main()
