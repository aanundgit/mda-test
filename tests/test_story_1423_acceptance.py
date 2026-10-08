"""Story 1423: one test per acceptance line, named after its Test Case so the pipeline can post each result.

The stack has no browser, so window widths are checked by reading the stylesheet the way a browser
applies it at that width: the base rules, then every @media (max-width) rule the width falls under.
"""
import re
import unittest

from test_page import Page, px, read, style_at, tab_stops

READABLE = 16
WIDE, NARROW = 1280, 375
CONTROLS = ("form", "input", "button", "select", "textarea")


class Story1423AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")
        self.page = Page(self.html)
        self.css = read("style.css")

    def text(self, tag, **attrs):
        return self.page.find(tag, **attrs)[0].text.strip()

    def assert_reads_well(self, width):
        main = style_at(self.css, "main", width)
        sides = 2 * px(main["padding"].split()[1], width)
        content = min(px(main["max-width"], width), width) - sides
        self.assertGreater(content, 0, f"no room for text at {width}px")
        self.assertLessEqual(content + sides, width, f"main is wider than a {width}px window")
        self.assertEqual(main.get("overflow-wrap"), "anywhere", "a long word could push the page sideways")

        sizes = {"h1": style_at(self.css, "h1", width).get("font-size"),
                 ".offer": style_at(self.css, ".offer", width).get("font-size"),
                 ".contact": style_at(self.css, ".contact", width).get("font-size", "1rem")}
        for selector, size in sizes.items():
            self.assertGreaterEqual(px(size, width), READABLE, f"{selector} at {width}px")
        self.assertGreaterEqual(float(style_at(self.css, "h1", width)["line-height"]), 1, "heading lines would overlap")

        # The three items stay in normal flow, one under the other, so nothing can sit on top of them or clip them.
        self.assertEqual(re.findall(r"(?<![\w-])(?:min-)?width:\s*\d+px", self.css), [])
        self.assertNotRegex(self.css, r"position:\s*(absolute|fixed)|float:|margin[\w-]*:[^;]*-\d|overflow(-x|-y)?:\s*hidden")

    def test_tc1429_ac1_a_customer_who_is_not_signed_in_opens_the_page_without_a_sign_in_prompt(self):
        """AC1, Test Case 1429."""
        self.assertEqual([tag for tag in CONTROLS if self.page.find(tag)], [], "nothing on the page asks for a sign-in")
        self.assertEqual(self.page.find("meta", **{"http-equiv": "refresh"}), [], "the page does not redirect")
        self.assertEqual(self.page.find("script"), [], "no script can send the customer to a sign-in page")

    def test_tc1429_ac2_the_page_shows_the_site_name_the_offer_line_and_the_contact_link_and_no_sign_in_payment_or_search_control(self):
        """AC2, Test Case 1429."""
        name, offer, contact = self.text("title"), self.text("p", class_="offer"), self.text("a", class_="contact")
        self.assertTrue(name and offer and contact)
        self.assertEqual(len(self.page.find("a", class_="contact")), 1, "one link to contact the team")
        self.assertEqual([tag for tag in CONTROLS if self.page.find(tag)], [], "no sign-in, payment, or search control")
        # Stories 1453 and 1459 added a banner and products between them: the header still opens the page with
        # the site name and offer line, and the contact link still closes it.
        self.assertEqual(" ".join(self.text("header").split()), f"{name} {offer}")
        self.assertTrue(" ".join(self.text("body").split()).endswith(contact))

    def test_tc1430_ac3_in_a_wide_window_the_three_items_are_readable_do_not_overlap_and_do_not_scroll_sideways(self):
        """AC3, Test Case 1430."""
        self.assert_reads_well(WIDE)

    def test_tc1430_ac4_in_a_narrow_window_the_three_items_are_readable_do_not_overlap_and_do_not_scroll_sideways(self):
        """AC4, Test Case 1430."""
        self.assertNotEqual(style_at(self.css, "main", NARROW), style_at(self.css, "main", WIDE), "the narrow rule applies")
        self.assert_reads_well(NARROW)

    def test_tc1431_ac5_tab_reaches_the_contact_link_with_a_visible_focus_style_and_enter_follows_it(self):
        """AC5, Test Case 1431."""
        contact = self.page.find("a", class_="contact")[0]
        self.assertIn(contact, tab_stops(self.page), "Tab reaches the contact link")
        self.assertNotIn("tabindex", contact.attrs)

        focus = style_at(self.css, ".contact:focus-visible", WIDE)
        width, line = focus["outline"].split()[:2]
        self.assertGreaterEqual(px(width, WIDE), 2, "the focus outline is easy to see")
        self.assertEqual(line, "solid")
        self.assertNotRegex(self.css, r"outline:\s*(none|0)\b", "no rule hides the focus outline")

        # Enter on a focused link with a real address opens it; there is no script to stop that.
        self.assertRegex(contact.attrs["href"], r"^https?://\S+$")


if __name__ == "__main__":
    unittest.main()
