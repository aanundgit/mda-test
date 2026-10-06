import unittest

from sample import ready


class ReadyTest(unittest.TestCase):
    def test_ready(self):
        self.assertTrue(ready())


if __name__ == "__main__":
    unittest.main()
