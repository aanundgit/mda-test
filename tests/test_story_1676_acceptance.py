"""Story 1676: one test per acceptance line, named after its Test Case so the pipeline can post each result.

Every check here is static. The stack has no browser and no JavaScript runtime, so nothing opens the page, clicks
Shop now, presses Tab, scrolls, or draws the page.
- index.html is read with html.parser. The trail tip is the element marked trail-tip. Its wording is a placeholder the
  team will replace, so only its label is read: it starts "Trail tip" and goes on to give a tip. It is then read
  against the page's heading, Shop now and its target, and every other region, link, and control.
- style.css is read the way a browser applies it at a window width (1280px wide, 375px narrow), with the
  [data-theme="dark"] rules added for the dark theme, through the same readers story 1666's acceptance tests use.
- "Under the heading" means after it in the heading's own stack, top to bottom. Other lines, such as story 1666's
  notice, may sit between them.
- Whether the tip fits one line is worked out from its length, its font size, and the room the banner leaves it,
  with a generous average letter width.
Not checked at runtime: the drawn layout (where lines wrap and what overlaps as rendered), a real click or key press,
where focus lands, and the scroll after Shop now. Prices, photos, and pages are outside this story and not checked.
"""
import re
import unittest

import test_story_1666_acceptance as story_1666
from test_page import REM, Page, contrast, px, read, script_problems, tab_stops
from test_story_1453_acceptance import READABLE, columns
from test_story_1641_acceptance import TEXT_CONTRAST, WIDE
from test_story_1654_acceptance import CONTROLS, ancestry, classes, describe, inside, link_problem, page_scripts
from test_story_1666_acceptance import LETTER, LINE_BREAKS, THEMES, WINDOWS, backdrop, inherited, room, style_of, words

TIP = "trail-tip"
LABELLED_TIP = re.compile(r"(?i)^trail\s+tips?\b\W+\w")  # "Trail tip", then the tip itself, whatever its words.


class Story1676AcceptanceTests(unittest.TestCase):
    # Story 1666's Then readers, borrowed so both stories read the banner the same way. Each takes the element to
    # check, so here they read the trail tip; each returns what is wrong, so an empty list is a pass.
    hidden_by = story_1666.Story1666AcceptanceTests.hidden_by
    covers = story_1666.Story1666AcceptanceTests.covers
    unwrapped = story_1666.Story1666AcceptanceTests.unwrapped
    not_working = story_1666.Story1666AcceptanceTests.not_working
    rest_of_page = story_1666.Story1666AcceptanceTests.rest_of_page

    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.body = self.page.find("body")[0]

    # The heading, the trail tip, and the rest of the page: the Given of every line.

    def heading(self):
        headings = self.page.find("h1")
        self.assertTrue(headings, "the home page has a heading")
        return headings[0]

    def trail_tip(self):
        """The first element in <body> marked as the trail tip. It must say it is a trail tip and give one."""
        tips = [e for e in self.page.elements if inside(e, self.body) and TIP in classes(e)]
        self.assertTrue(tips, "the home page has a trail tip")
        self.assertRegex(words(tips[0]), LABELLED_TIP, "the trail tip says it is a trail tip and gives a tip")
        return tips[0]

    def not_under(self, heading, tip, width):
        """Why the tip would not show under the heading in this window: it, or the element that holds it, must come
        after the heading in the heading's parent, that parent must stack its children top to bottom, and none of them
        may be moved out of that order. Other lines may sit between the heading and the tip."""
        parent = heading.parent
        holder = next((el for el in ancestry(tip) if el.parent is parent), None)
        if holder is None:
            return [f"the trail tip sits outside {describe(parent)}, the heading's parent"]
        siblings = [e for e in self.page.elements if e.parent is parent]
        found = [] if siblings.index(holder) > siblings.index(heading) else ["the trail tip comes before the heading"]
        layout = style_of(self.css, parent, width)
        display = layout.get("display", "block").strip()
        if display in ("flex", "inline-flex"):
            stacked = layout.get("flex-direction", "row").strip() == "column"
        elif display in ("grid", "inline-grid"):
            template = layout.get("grid-template-columns", "none").strip()
            stacked = (template == "none" or columns(template) == 1) and "column" not in layout.get("grid-auto-flow", "")
        else:
            stacked = display in ("block", "flow-root", "list-item")
        if not stacked:
            found.append(f"{describe(parent)} lays its children side by side ({display}) at {width}px")
        for el in [heading, holder] + ([tip] if tip is not holder else []):
            style = style_of(self.css, el, width)
            if style.get("position", "static").strip() in ("absolute", "fixed"):
                found.append(f"{describe(el)} is taken out of the page flow at {width}px")
            found += [f"{describe(el)} has {p}: {style[p]} at {width}px" for p in ("order", "grid-row", "grid-area", "float")
                      if style.get(p, "auto").strip() not in ("0", "auto", "none")]
        return found

    def test_tc1680_ac1_a_one_line_trail_tip_appears_under_the_heading_in_wide_and_narrow_windows(self):
        """AC1, Test Case 1680. Static: the tip's label and place in index.html, and the stylesheet at each width.
        Not run: the page drawn in a browser."""
        # Given a customer opens the home page.
        heading = self.heading()
        # When the page loads, in a wide window (Test Case step 1) or a narrow window (step 2).
        tip = self.trail_tip()
        # Then a trail tip appears under the heading.
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                self.assertEqual(self.hidden_by(heading, width), [], "the heading shows")
                self.assertEqual(self.hidden_by(tip, width), [], "the trail tip shows")
                self.assertEqual(self.not_under(heading, tip, width), [])
        # And it is one line (step 1): nothing inside it starts a new line, and its words fit the wide window's banner
        # on one line.
        breaks = [describe(e) for e in self.page.elements if inside(e, tip) and e.tag in LINE_BREAKS]
        self.assertEqual(breaks, [], "nothing inside the trail tip starts a new line")
        size = px(inherited(self.css, tip, "font-size", WIDE, "light", f"{REM}px"), WIDE)
        needed, space = len(words(tip)) * LETTER * size, room(self.css, tip, WIDE)
        self.assertLessEqual(needed, space, f"about {needed:.0f}px of words in a {space:.0f}px line in a wide window")

    def test_tc1681_ac2_with_the_trail_tip_shown_shop_now_works_as_before_in_wide_and_narrow_windows(self):
        """AC2, Test Case 1681. Static: Shop now's address and target, the scripts, and the stylesheet at each width.
        Not run: a real click or key press, or the scroll it causes."""
        # Given the trail tip is shown on the home page.
        tip = self.trail_tip()
        shop_now = [a for a in self.page.find("a") if words(a) == "Shop now"]
        self.assertEqual(len(shop_now), 1, "the home page has one Shop now")
        shop_now = shop_now[0]
        # When the customer selects Shop now: it can be reached with Tab and pressed, and is not disabled.
        self.assertTrue(any(s is shop_now for s in tab_stops(self.page)), "Shop now can be reached from the keyboard")
        self.assertFalse({"disabled", "aria-disabled"} & shop_now.attrs.keys(), "Shop now is not disabled")
        self.assertEqual(script_problems(self.page), [], "no script stops the link or sends the customer elsewhere")
        # Then Shop now works as it did before the trail tip was added: it leads to the products section on this page,
        # which takes focus without becoming a Tab stop.
        href = shop_now.attrs.get("href", "").strip()
        self.assertTrue(href.startswith("#"), "Shop now stays on this page")
        self.assertIsNone(link_problem(self.page, href), href)
        target = next(e for e in self.page.elements if e.attrs.get("id") == href[1:])
        self.assertIn("products", classes(target), "Shop now still leads to the products section")
        self.assertEqual(target.attrs.get("tabindex"), "-1", "the products section takes focus without becoming a Tab stop")
        # The same in a wide window (Test Case step 1) and a narrow window (step 2): the tip shows, Shop now shows and
        # can be selected, the tip cannot lie over it, and the products section shows.
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                self.assertEqual(self.hidden_by(tip, width), [], "the trail tip is shown")
                self.assertEqual(self.hidden_by(shop_now, width), [], "Shop now shows and can be selected")
                self.assertEqual(self.covers(tip, width), [], "the trail tip cannot lie over Shop now")
                self.assertEqual(self.hidden_by(target, width), [], "the products section shows")

    def test_tc1682_ac3_the_trail_tip_reads_under_the_heading_and_the_rest_of_the_page_shows_and_works_in_wide_and_narrow_windows(self):
        """AC3, Test Case 1682. Static: contrast, size, wrapping, and position from the stylesheet at each width, and
        every other link and control's target and wiring. Not run: a browser render, scrolling, real clicks, or Tab."""
        # Given the home page shows the trail tip.
        heading, tip = self.heading(), self.trail_tip()
        rest = self.rest_of_page(tip)
        uses = [e for e in rest if (e.tag == "a" and e.attrs.get("href")) or e.tag in CONTROLS]
        self.assertTrue(uses, "the rest of the home page has links and controls")
        stops, scripts = tab_stops(self.page), [code for _, code in page_scripts(self.page)]
        self.assertEqual(script_problems(self.page), [], "no script stops a link")
        # When it is viewed in a wide window (Test Case step 1) and in a narrow window (step 2).
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                # Then the trail tip is readable under the heading: it shows under it, its words keep body-text
                # contrast in either theme and body-text size, they wrap to the window, and nothing cuts them off.
                self.assertEqual(self.hidden_by(tip, width), [], "the trail tip shows")
                self.assertEqual(self.not_under(heading, tip, width), [])
                for theme in THEMES:
                    colour = inherited(self.css, tip, "color", width, theme, "#000")
                    self.assertGreaterEqual(contrast(colour, backdrop(self.css, tip, width, theme)), TEXT_CONTRAST,
                                            f"the trail tip's words in the {theme} theme")
                size = px(inherited(self.css, tip, "font-size", width, "light", f"{REM}px"), width)
                self.assertGreaterEqual(size, READABLE, "the trail tip's words are at least body-text size")
                self.assertEqual(self.unwrapped(tip, width), [], "the trail tip wraps to the window")
                # Test Case step 2: the trail tip does not cover other content.
                self.assertEqual(self.covers(tip, width), [], "the trail tip does not cover other content")
                # And the rest of the page shows and works as before: each region, heading, photo, text, link, and
                # control, story 1666's notice among them, shows, and each link and control can be reached from the
                # keyboard and goes somewhere or is wired to a script.
                for e in rest:
                    self.assertEqual(self.hidden_by(e, width), [], describe(e))
                for e in uses:
                    self.assertEqual(self.not_working(e, stops, scripts), [], f"{describe(e)} {words(e)}")


if __name__ == "__main__":
    unittest.main()
