import re
import unittest
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


@dataclass
class Element:
    tag: str
    attrs: dict
    text: str = field(default="")


class Page(HTMLParser):
    """Every element on a page, with its attributes and its text, in page order."""

    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.open = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.elements.append(element)
        if tag not in VOID:
            self.open.append(element)

    def handle_endtag(self, tag):
        while self.open:
            if self.open.pop().tag == tag:
                break

    def handle_data(self, data):
        for element in self.open:
            element.text += data

    def find(self, tag, **attrs):
        """Elements by tag and attributes. class_ matches the class attribute."""
        wanted = {key.rstrip("_"): value for key, value in attrs.items()}
        return [e for e in self.elements if e.tag == tag and all(e.attrs.get(k) == v for k, v in wanted.items())]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class PageTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))

    def test_the_page_names_its_language(self):
        self.assertTrue(self.page.find("html")[0].attrs.get("lang"))

    def test_the_page_fits_the_window_width(self):
        self.assertEqual(self.page.find("meta", name="viewport")[0].attrs["content"], "width=device-width, initial-scale=1")

    def test_the_stylesheet_is_linked_and_exists(self):
        link = self.page.find("link", rel="stylesheet")[0]
        self.assertTrue((ROOT / link.attrs["href"]).is_file())

    def test_the_page_has_one_main_landmark(self):
        self.assertEqual(len(self.page.find("main")), 1)


class HomePageTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))

    def text(self, tag, **attrs):
        return self.page.find(tag, **attrs)[0].text.strip()

    def test_the_site_name_is_the_only_main_heading(self):
        self.assertEqual(len(self.page.find("h1")), 1)
        self.assertTrue(self.text("h1"))

    def test_the_page_title_is_the_site_name(self):
        self.assertEqual(self.text("title"), self.text("h1"))

    def test_main_holds_the_site_name_the_offer_line_and_the_contact_link_in_that_order(self):
        main = self.text("main")
        name, offer, contact = self.text("h1"), self.text("p", class_="offer"), self.text("a", class_="contact")
        self.assertTrue(name and offer and contact)
        self.assertLess(main.index(name), main.index(offer))
        self.assertLess(main.index(offer), main.index(contact))

    def test_the_contact_link_goes_to_a_web_address(self):
        self.assertRegex(self.page.find("a", class_="contact")[0].attrs["href"], r"^https?://")

    def test_the_page_has_no_sign_in_payment_or_search_control(self):
        for tag in ("form", "input", "button", "select", "textarea"):
            self.assertEqual(self.page.find(tag), [], tag)


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.css = read("style.css")

    def test_the_stylesheet_has_a_narrow_window_rule(self):
        self.assertRegex(self.css, r"@media \(max-width: \d+px\)")

    def test_no_fixed_width_can_push_the_page_sideways(self):
        self.assertEqual(re.findall(r"(?<![\w-])(?:min-)?width:\s*\d+px", self.css), [])

    def test_long_words_wrap_instead_of_scrolling_sideways(self):
        self.assertIn("overflow-wrap: anywhere", self.css)

    def test_the_contact_link_shows_a_visible_focus_outline(self):
        self.assertRegex(self.css, r"\.contact:focus-visible\s*\{[^}]*outline:\s*\d+px solid")


if __name__ == "__main__":
    unittest.main()
