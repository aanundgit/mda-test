import re
import unittest
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
REM = 16  # Browser default root font size; the stylesheet does not change it.
PRODUCTS = ["Four-person tent", "Day-hiking backpack", "Waterproof hiking jacket", "Hiking boots"]
WEB_PHOTO_BYTES = 300_000


@dataclass
class Element:
    tag: str
    attrs: dict
    text: str = field(default="")
    parent: "Element | None" = field(default=None, repr=False)


class Page(HTMLParser):
    """Every element on a page, with its attributes, its text, and its parent, in page order."""

    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.open = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs), parent=self.open[-1] if self.open else None)
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

    def within(self, ancestor, tag):
        """Elements by tag anywhere inside ancestor."""
        def inside(element):
            while element.parent is not None:
                element = element.parent
                if element is ancestor:
                    return True
            return False
        return [e for e in self.elements if e.tag == tag and inside(e)]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def blocks(css):
    """Top-level (prelude, body) pairs, keeping the rules nested inside an @media block in its body."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found, depth, head, start = [], 0, 0, 0
    for i, char in enumerate(css):
        if char == "{":
            if depth == 0:
                prelude, start = css[head:i].strip(), i + 1
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                found.append((prelude, css[start:i]))
                head = i + 1
    return found


def style_at(css, selector, width):
    """The declarations a browser applies to selector in a window this many pixels wide."""
    applied = {}
    for prelude, body in blocks(css):
        media = re.fullmatch(r"@media \(max-width: (\d+)px\)", prelude)
        inner = blocks(body) if media else [(prelude, body)]
        if media and width > int(media.group(1)):
            continue
        for selectors, declarations in inner:
            if selector in (s.strip() for s in selectors.split(",")):
                applied.update(re.findall(r"([\w-]+)\s*:\s*([^;]+);", declarations))
    return applied


def px(value, width):
    def one(part):
        number, unit = re.fullmatch(r"([\d.]+)(rem|vw|px)", part.strip()).groups()
        return float(number) * {"rem": REM, "vw": width / 100, "px": 1}[unit]

    clamp = re.fullmatch(r"clamp\((.+),(.+),(.+)\)", value)
    if clamp:
        low, preferred, high = map(one, clamp.groups())
        return max(low, min(preferred, high))
    return one(value)


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
        self.assertEqual(self.text("h1"), "Northwind Outdoor")

    def test_the_page_title_is_the_site_name(self):
        self.assertEqual(self.text("title"), self.text("h1"))

    def test_the_header_holds_the_site_name_and_offer_line_and_the_footer_holds_the_contact_link(self):
        header, footer = self.page.find("header")[0], self.page.find("footer")[0]
        self.assertEqual([e.text.strip() for e in self.page.within(header, "h1")], [self.text("h1")])
        self.assertEqual(len(self.page.within(header, "p")), 1)
        self.assertEqual([e.attrs.get("class") for e in self.page.within(footer, "a")], ["contact"])

    def test_the_contact_link_goes_to_a_web_address(self):
        self.assertRegex(self.page.find("a", class_="contact")[0].attrs["href"], r"^https?://")

    def test_the_page_has_no_sign_in_payment_or_search_control(self):
        for tag in ("form", "input", "button", "select", "textarea"):
            self.assertEqual(self.page.find(tag), [], tag)


class ProductCardTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.cards = self.page.find("li", class_="product-card")

    def test_the_products_section_is_labelled_by_its_own_heading(self):
        section = self.page.find("section", class_="products")[0]
        heading = self.page.find("h2", id=section.attrs["aria-labelledby"])[0]
        self.assertTrue(heading.text.strip())
        self.assertIn(heading, self.page.within(section, "h2"))

    def test_there_is_one_card_for_each_product_in_order(self):
        self.assertEqual([self.page.within(card, "h3")[0].text.strip() for card in self.cards], PRODUCTS)

    def test_each_card_has_one_described_photo_a_name_and_a_one_line_description(self):
        for card in self.cards:
            photos, names, lines = (self.page.within(card, tag) for tag in ("img", "h3", "p"))
            self.assertEqual((len(photos), len(names), len(lines)), (1, 1, 1))
            self.assertTrue(photos[0].attrs.get("alt", "").strip(), photos[0].attrs.get("src"))
            self.assertTrue(lines[0].text.strip())

    def test_each_photo_exists_and_declares_its_real_size_so_the_page_does_not_shift(self):
        for photo in self.page.find("img"):
            path = ROOT / photo.attrs["src"]
            self.assertTrue(path.is_file(), path)
            self.assertRegex(photo.attrs.get("width", ""), r"^\d+$")
            self.assertRegex(photo.attrs.get("height", ""), r"^\d+$")

    def test_each_photo_is_small_enough_for_the_web(self):
        for photo in self.page.find("img"):
            self.assertLessEqual((ROOT / photo.attrs["src"]).stat().st_size, WEB_PHOTO_BYTES, photo.attrs["src"])

    def test_each_photo_is_credited_with_its_licence(self):
        credits = read("images/CREDITS.md")
        self.assertIn("Unsplash License", credits)
        for photo in self.page.find("img"):
            self.assertIn(f"| {Path(photo.attrs['src']).name} |", credits)

    def test_no_price_or_cart_appears(self):
        self.assertNotRegex(self.page.find("body")[0].text, r"(?i)[$€£]\s*\d|\bprice\b|\bcart\b")


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

    def test_the_cards_sit_four_in_a_row_when_wide_and_one_per_row_when_narrow(self):
        self.assertEqual(style_at(self.css, ".product-grid", 1280)["grid-template-columns"], "repeat(4, minmax(0, 1fr))")
        self.assertEqual(style_at(self.css, ".product-grid", 375)["grid-template-columns"], "minmax(0, 1fr)")

    def test_photos_fill_the_card_width_and_keep_their_shape(self):
        photo = style_at(self.css, ".product-card img", 1280)
        self.assertEqual((photo["width"], photo["height"], photo["object-fit"]), ("100%", "auto", "cover"))
        self.assertIn("aspect-ratio", photo)


if __name__ == "__main__":
    unittest.main()
