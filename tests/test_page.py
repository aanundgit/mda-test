import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    """Every start tag on a page, with its attributes, in page order."""

    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def find(self, tag, **attrs):
        return [found for name, found in self.tags if name == tag and all(found.get(k) == v for k, v in attrs.items())]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class PageTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))

    def test_the_page_names_its_language(self):
        self.assertTrue(self.page.find("html")[0].get("lang"))

    def test_the_page_fits_the_window_width(self):
        self.assertEqual(self.page.find("meta", name="viewport")[0]["content"], "width=device-width, initial-scale=1")

    def test_the_stylesheet_is_linked_and_exists(self):
        link = self.page.find("link", rel="stylesheet")[0]
        self.assertTrue((ROOT / link["href"]).is_file())

    def test_the_page_has_one_main_landmark(self):
        self.assertEqual(len(self.page.find("main")), 1)


class StyleTests(unittest.TestCase):
    def test_the_stylesheet_has_a_narrow_window_rule(self):
        self.assertRegex(read("style.css"), r"@media \(max-width: \d+px\)")


if __name__ == "__main__":
    unittest.main()
