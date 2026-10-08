"""Story 1459: one test per acceptance line, named after its Test Case so the pipeline can post each result.

The stack has no browser, so window widths are checked by reading the stylesheet the way a browser
applies it at that width. Text contrast is checked against the worst case: the overlay laid over a pure
white pixel, which is brighter than any part of the photo can be.
"""
import re
import unittest

from test_page import ROOT, Page, contrast, px, read, style_at, tab_stops

WIDE, NARROW = 1280, 375
READABLE = 16
TEXT_CONTRAST = 4.5  # WCAG AA for body-size text; the headline is large, which needs only 3:1.
OUTLINE_CONTRAST = 3  # WCAG AA for a focus indicator against what is next to it.
HEADLINE = "Gear up for your next trail"


def over_white(overlay):
    """The colour a translucent black overlay gives over pure white, as (r, g, b)."""
    alpha = float(re.fullmatch(r"rgb\(0 0 0 / ([\d.]+)\)", overlay).group(1))
    return (round(255 * (1 - alpha)),) * 3


class Story1459AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.banner = self.page.find("section", class_="banner")[0]
        self.photo = self.page.within(self.banner, "img")[0]
        self.shop_now = self.page.find("a", class_="shop-now")[0]

    def assert_photo_covers_the_banner_with_the_text_on_it(self, width):
        self.assertEqual(style_at(self.css, ".banner", width)["display"], "grid")
        self.assertEqual(style_at(self.css, ".banner > *", width)["grid-area"], "1 / 1", "photo and text share one cell")
        photo = style_at(self.css, ".banner-photo", width)
        self.assertEqual((photo["width"], photo["height"]), ("100%", "100%"), "the photo fills the cell the text sits in")
        self.assertEqual(photo["object-fit"], "cover", "the photo is cropped, never stretched")

    def assert_no_sideways_scroll(self, width):
        self.assertEqual(re.findall(r"(?<![\w-])(?:min-)?width:\s*\d+px", self.css), [], "a fixed width")
        self.assertNotRegex(self.css, r"position:\s*(absolute|fixed)|float:|margin[\w-]*:[^;]*-\d|overflow(-x|-y)?:\s*hidden")
        self.assertEqual(style_at(self.css, ".banner", width).get("overflow-wrap"), "anywhere", "a long headline word wraps")

    def test_tc1468_ac1_below_the_header_a_campsite_photo_fills_the_width_with_the_headline_and_shop_now_on_it(self):
        """AC1, Test Case 1468."""
        order = [e for e in self.page.elements if e.tag in ("header", "main") or e is self.banner]
        self.assertEqual([e.tag for e in order], ["header", "section", "main"], "the banner sits right below the header")
        self.assertIs(self.banner.parent, self.page.find("body")[0], "the banner is outside main's narrow column")
        self.assertEqual(style_at(self.css, "body", WIDE)["margin"], "0")
        self.assertFalse({"max-width", "margin", "padding"} & style_at(self.css, ".banner", WIDE).keys(), "nothing narrows the banner")
        self.assertTrue((ROOT / self.photo.attrs["src"]).is_file())
        self.assertEqual([h.text.strip() for h in self.page.within(self.banner, "h1")], [HEADLINE])
        self.assertIn(self.shop_now, self.page.within(self.banner, "a"))
        self.assertEqual(self.shop_now.text.strip(), "Shop now")
        self.assert_photo_covers_the_banner_with_the_text_on_it(WIDE)

    def test_tc1468_ac2_the_headline_and_button_label_stand_out_clearly_from_the_photo(self):
        """AC2, Test Case 1468."""
        for width in (WIDE, NARROW):
            text = style_at(self.css, ".banner-text", width)
            worst = over_white(text["background"])
            self.assertGreaterEqual(contrast(text["color"], worst), TEXT_CONTRAST, f"white text over the brightest photo at {width}px")
            button = style_at(self.css, ".shop-now", width)
            self.assertGreaterEqual(contrast(button["color"], button["background"]), TEXT_CONTRAST, "Shop now label on its fill")
            self.assertGreaterEqual(px(style_at(self.css, "h1", width)["font-size"], width), 24, "the headline is large text")

    def test_tc1468_ac3_in_a_wide_window_the_photo_spans_the_width_unstretched_with_the_headline_and_button_on_it(self):
        """AC3, Test Case 1468."""
        self.assert_photo_covers_the_banner_with_the_text_on_it(WIDE)
        tall = px(style_at(self.css, ".banner", WIDE)["min-height"], WIDE)
        self.assertGreaterEqual(tall / WIDE, 0.3, f"the banner is {tall:.0f}px tall, enough to read as a wide photo")
        self.assertEqual((self.photo.attrs["width"], self.photo.attrs["height"]), ("1600", "700"), "the file is a wide crop")
        self.assert_no_sideways_scroll(WIDE)

    def test_tc1468_ac4_in_a_narrow_window_the_photo_fits_the_headline_and_button_stay_visible_and_nothing_scrolls_sideways(self):
        """AC4, Test Case 1468."""
        self.assert_photo_covers_the_banner_with_the_text_on_it(NARROW)
        self.assertLess(px(style_at(self.css, "h1", NARROW)["font-size"], NARROW),
                        px(style_at(self.css, "h1", WIDE)["font-size"], WIDE), "the headline shrinks to fit")
        self.assertGreaterEqual(px(style_at(self.css, ".banner", NARROW)["min-height"], NARROW), 16 * 16,
                                "the banner keeps room for a two-line headline and the button")
        self.assert_no_sideways_scroll(NARROW)
        # The rest of the page: the header, cards, and footer keep their narrow-window rules.
        for selector in (".site-name", ".offer"):
            self.assertGreaterEqual(px(style_at(self.css, selector, NARROW)["font-size"], NARROW), READABLE, selector)
        self.assertEqual(style_at(self.css, ".product-grid", NARROW)["grid-template-columns"], "minmax(0, 1fr)")
        self.assertEqual(style_at(self.css, "main", NARROW)["overflow-wrap"], "anywhere")

    def test_tc1469_ac5_a_screen_reader_hears_a_short_description_of_the_campsite_photo(self):
        """AC5, Test Case 1469."""
        alt = self.photo.attrs.get("alt", "").strip()
        self.assertGreaterEqual(len(alt.split()), 4, "a description, not a label")
        self.assertRegex(alt, r"(?i)\btent\b", "the description says what the photo shows")
        self.assertNotRegex(alt, r"(?i)\.(jpe?g|png|webp)\b|^(image|photo|picture) of")
        self.assertFalse({"aria-hidden", "role"} & self.photo.attrs.keys(), "the photo is not hidden from a screen reader")

    def test_tc1469_ac6_tab_reaches_shop_now_with_a_visible_focus_style_and_enter_moves_to_the_products(self):
        """AC6, Test Case 1469."""
        self.assertIs(tab_stops(self.page)[0], self.shop_now, "the first Tab lands on Shop now")
        width, line, colour = style_at(self.css, ".shop-now:focus-visible", WIDE)["outline"].split()
        self.assertGreaterEqual(px(width, WIDE), 2, "the focus outline is easy to see")
        self.assertEqual(line, "solid")
        worst = over_white(style_at(self.css, ".banner-text", WIDE)["background"])
        self.assertGreaterEqual(contrast(colour, worst), OUTLINE_CONTRAST, "the outline stands out on the photo")
        self.assertNotRegex(self.css, r"outline:\s*(none|0)\b", "no rule hides the focus outline")

        # Enter on an in-page link moves to its target; tabindex -1 lets the target take focus too.
        target = self.page.find("section", id=self.shop_now.attrs["href"].removeprefix("#"))
        self.assertEqual([t.attrs.get("class") for t in target], ["products"])
        self.assertEqual(target[0].attrs.get("tabindex"), "-1")
        self.assertEqual(self.page.find("script"), [], "no script can stop the link")


if __name__ == "__main__":
    unittest.main()
