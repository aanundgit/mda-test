"""Story 1453: one test per acceptance line, named after its Test Case so the pipeline can post each result.

The stack has no browser, so window widths are checked by reading the stylesheet the way a browser
applies it at that width, and card widths are worked out from the main column, its padding, and the grid gap.
"""
import re
import unittest

from test_page import ROOT, Page, px, read, style_at

WIDE, NARROW = 1280, 375
READABLE = 16
CARD_MIN = 200  # Narrower than this, a card's name and description start breaking mid-word.
CONTRAST = 4.5  # WCAG AA for body-size text.
CONTROLS = ("form", "input", "button", "select", "textarea")
PRODUCTS = ["Four-person tent", "Day-hiking backpack", "Waterproof hiking jacket", "Hiking boots"]


def luminance(colour):
    digits = colour.lstrip("#")
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    channels = [int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def columns(value):
    repeat = re.match(r"repeat\((\d+),", value)
    return int(repeat.group(1)) if repeat else len(re.findall(r"minmax\([^)]*\)|\S+", value))


class Story1453AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.cards = self.page.find("li", class_="product-card")

    def card_width(self, width):
        main = style_at(self.css, "main", width)
        grid = style_at(self.css, ".product-grid", width)
        content = min(px(main["max-width"], width), width) - 2 * px(main["padding"].split()[1], width)
        count, gap = columns(grid["grid-template-columns"]), px(grid["gap"], width)
        return count, (content - gap * (count - 1)) / count

    def assert_header_and_footer_read_well(self, width):
        header = style_at(self.css, ".site-header", width)
        self.assertGreaterEqual(contrast(header["color"], header["background"]), CONTRAST, "header text on its green")
        for selector in ("h1", ".offer"):
            self.assertGreaterEqual(px(style_at(self.css, selector, width)["font-size"], width), READABLE, selector)
        footer = self.page.find("footer")[0]
        self.assertEqual([e.attrs.get("class") for e in self.page.within(footer, "a")], ["contact"])
        self.assertNotIn("font-size", style_at(self.css, ".contact", width), "the contact link keeps the body size")

    def assert_nothing_overlaps_or_is_cut_off(self):
        self.assertEqual(re.findall(r"(?<![\w-])(?:min-)?width:\s*\d+px", self.css), [], "a fixed width")
        self.assertNotRegex(self.css, r"position:\s*(absolute|fixed)|float:|margin[\w-]*:[^;]*-\d|overflow(-x|-y)?:\s*hidden")
        photo = style_at(self.css, ".product-card img", WIDE)
        self.assertEqual((photo["width"], photo["height"], photo["object-fit"]), ("100%", "auto", "cover"))
        self.assertEqual(style_at(self.css, "main", WIDE).get("overflow-wrap"), "anywhere", "long words wrap")

    def test_tc1465_ac1_a_customer_who_is_not_signed_in_opens_the_page_and_the_header_shows_northwind_outdoor(self):
        """AC1, Test Case 1465."""
        self.assertEqual([tag for tag in CONTROLS if self.page.find(tag)], [], "nothing asks for a sign-in")
        self.assertEqual(self.page.find("meta", **{"http-equiv": "refresh"}), [], "the page does not redirect")
        self.assertEqual(self.page.find("script"), [], "no script can send the customer to a sign-in page")
        header = self.page.find("header")[0]
        self.assertEqual([e.text.strip() for e in self.page.within(header, "h1")], ["Northwind Outdoor"])

    def test_tc1465_ac2_four_product_cards_each_have_a_photo_name_and_description_and_no_price_cart_or_sign_in(self):
        """AC2, Test Case 1465."""
        section = self.page.find("section", class_="products")[0]
        self.assertEqual([c for c in self.cards if c not in self.page.within(section, "li")], [], "cards sit in the products section")
        self.assertEqual([self.page.within(card, "h3")[0].text.strip() for card in self.cards], PRODUCTS)
        for card in self.cards:
            photo, line = self.page.within(card, "img")[0], self.page.within(card, "p")[0]
            self.assertTrue((ROOT / photo.attrs["src"]).is_file(), photo.attrs["src"])
            self.assertTrue(line.text.strip())
        body = self.page.find("body")[0].text
        self.assertEqual([tag for tag in CONTROLS if self.page.find(tag)], [], "no cart or sign-in control")
        self.assertNotRegex(body, r"(?i)[$€£]\s*\d|\bprice\b|\bcart\b|\bsign[ -]?in\b|\blog[ -]?in\b")

    def test_tc1466_ac3_in_a_wide_window_the_four_cards_sit_in_one_row_and_nothing_overlaps_or_is_cut_off(self):
        """AC3, Test Case 1466."""
        count, card = self.card_width(WIDE)
        self.assertEqual(count, len(self.cards), "all four cards fit in one row")
        self.assertGreaterEqual(card, CARD_MIN, f"each card is {card:.0f}px wide")
        self.assert_nothing_overlaps_or_is_cut_off()
        self.assert_header_and_footer_read_well(WIDE)

    def test_tc1466_ac4_in_a_narrow_window_the_cards_sit_one_per_row_fit_the_width_and_do_not_scroll_sideways(self):
        """AC4, Test Case 1466."""
        count, card = self.card_width(NARROW)
        self.assertEqual(count, 1, "one card per row")
        self.assertGreaterEqual(card, CARD_MIN, f"each card is {card:.0f}px wide")
        self.assertLessEqual(card, NARROW, "a card is wider than the window")
        self.assertLess(px(style_at(self.css, "h1", NARROW)["font-size"], NARROW),
                        px(style_at(self.css, "h1", WIDE)["font-size"], WIDE), "the site name shrinks to fit")
        self.assert_nothing_overlaps_or_is_cut_off()
        self.assert_header_and_footer_read_well(NARROW)

    def test_tc1467_ac5_a_screen_reader_hears_a_short_description_of_each_product_photo(self):
        """AC5, Test Case 1467."""
        descriptions = []
        for card in self.cards:
            photo = self.page.within(card, "img")[0]
            alt = photo.attrs.get("alt", "").strip()
            self.assertGreaterEqual(len(alt.split()), 4, f"{photo.attrs['src']} needs a description, not a label")
            self.assertNotRegex(alt, r"(?i)\.(jpe?g|png|webp)\b|^(image|photo|picture) of", alt)
            self.assertFalse({"aria-hidden", "role"} & photo.attrs.keys(), "the photo is not hidden from a screen reader")
            descriptions.append(alt)
        self.assertEqual(len(set(descriptions)), len(descriptions), "each photo has its own description")

    def test_tc1467_ac6_tab_reaches_the_footer_contact_link_with_a_visible_focus_style_and_enter_follows_it(self):
        """AC6, Test Case 1467."""
        focusable = [e for e in self.page.elements
                     if (e.tag == "a" and e.attrs.get("href")) or e.tag in CONTROLS[1:] or "tabindex" in e.attrs]
        contact = self.page.find("a", class_="contact")[0]
        self.assertIn(contact, self.page.within(self.page.find("footer")[0], "a"))
        self.assertIn(contact, focusable, "Tab can reach the contact link")
        self.assertFalse([e for e in self.page.elements if e.attrs.get("tabindex", "0").lstrip("-") != "0"],
                         "no tabindex reorders or skips the page")

        width, line = style_at(self.css, ".contact:focus-visible", WIDE)["outline"].split()[:2]
        self.assertGreaterEqual(px(width, WIDE), 2, "the focus outline is easy to see")
        self.assertEqual(line, "solid")
        self.assertNotRegex(self.css, r"outline:\s*(none|0)\b", "no rule hides the focus outline")

        # Enter on a focused link with a real address opens it; there is no script to stop that.
        self.assertRegex(contact.attrs["href"], r"^https?://\S+$")


if __name__ == "__main__":
    unittest.main()
