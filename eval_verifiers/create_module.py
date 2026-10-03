import unittest

from slug import slugify


class HiddenTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_edge_cases(self):
        self.assertEqual(slugify("  A---B  "), "a-b")
        self.assertEqual(slugify("---"), "")
        self.assertEqual(slugify("X"), "x")


if __name__ == "__main__":
    unittest.main()
