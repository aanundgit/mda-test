"""Story 1666: one test per acceptance line, named after its Test Case so the pipeline can post each result.

Every check here is static. The stack has no browser and no JavaScript runtime, so nothing opens the page, clicks
Shop now, presses Tab, scrolls, or draws the page.
- index.html is read with html.parser. The notice is found by its words wherever it is on the page, then read against
  the page's heading, Shop now and its target, and every other region, link, and control.
- style.css is read the way a browser applies it at a window width (1280px wide, 375px narrow), with the
  [data-theme="dark"] rules added for the dark theme. An element takes the rules on its tag, classes, and id, alone or
  after an element it sits in (".banner-text p", ".banner > *"), and inherits colour, font size, and white-space.
- Whether the notice fits one line is worked out from its length, its font size, and the room the banner leaves it,
  with a generous average letter width.
Not checked at runtime: the drawn layout (where lines wrap and what overlaps as rendered), a real click or key press,
where focus lands, and the scroll after Shop now. Prices, photos, and pages are outside this story and not checked.
"""
import re
import unittest
from functools import lru_cache

from test_page import DARK, REM, Page, blocks, contrast, px, read, script_problems, style_at, tab_stops
from test_story_1453_acceptance import READABLE, columns
from test_story_1459_acceptance import over_white
from test_story_1641_acceptance import NARROW, TEXT_CONTRAST, WIDE
from test_story_1654_acceptance import CONTROLS, HIDES, ancestry, classes, describe, inside, link_problem, page_scripts, selectors

WINDOWS = {"wide": WIDE, "narrow": NARROW}
THEMES = ("light", "dark")
NOTICE = re.compile(r"(?i)\bweekend\s+workshops\s+are\s+full\b")
LETTER = 0.6  # A generous average letter width, in em, for system-ui at weight 600; real text runs narrower.
LINE_BREAKS = {"br", "p", "div", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "table", "hr", "blockquote"}
SHOWN = ("h1", "h2", "h3", "h4", "h5", "h6", "img", "p", "li", *CONTROLS)
FIXED = re.compile(r"[\d.]+(px|rem|vw)")


def words(e):
    return " ".join(e.text.split())


@lru_cache(maxsize=None)
def sheet(css, width):
    """{selector: what style_at gives it at this window width} for every selector the stylesheet names."""
    names = set()
    for prelude, body in blocks(css):
        for group, _ in blocks(body) if prelude.startswith("@") else [(prelude, body)]:
            names.update(s.strip() for s in group.split(","))
    return {name: style_at(css, name, width) for name in names}


def matching(e):
    """Selectors that can match e: its tag, classes, and id, alone, after its parent (">"), or after any element it
    sits in (a space)."""
    own, chain = selectors(e), ancestry(e)[1:]
    found = list(own)
    for i, el in enumerate(chain):
        for outer in selectors(el):
            found += [f"{outer} {s}" for s in own]
            if i == 0:
                found += [f"{outer} > {s}" for s in [*own, "*"]]
    return found


def style_of(css, e, width, theme="light"):
    """The declarations e gets at this width and theme. A dark rule repeats a selector after [data-theme="dark"]."""
    rules, names = sheet(css, width), matching(e)
    applied = {}
    for name in names:
        applied.update(rules.get(name, {}))
    if theme == "dark":
        for name in names:
            applied.update(rules.get(f"{DARK} {name}", {}))
    return applied


def inherited(css, e, prop, width, theme, default):
    """prop as e shows it: its own value, else the nearest one set on an element it sits in, else the browser's."""
    for el in ancestry(e):
        value = style_of(css, el, width, theme).get(prop, "inherit").strip()
        if value not in ("inherit", "currentColor"):
            return value
    return default


def backdrop(css, e, width, theme):
    """What e's text sits on: the nearest fill on it or an element it sits in. A translucent black overlay is taken
    over pure white, the brightest the banner photo can be (story 1459)."""
    for el in ancestry(e):
        style = style_of(css, el, width, theme)
        fill = style.get("background-color", style.get("background", "transparent")).strip()
        if fill.startswith("rgb(0 0 0 /"):
            return over_white(fill)
        if fill != "transparent":
            return fill
    return "#fff"


def length(value, width):
    """A CSS length in px; 0 and auto count as nothing."""
    value = value.strip()
    return 0.0 if value in ("0", "auto") else px(value, width)


def sides(value):
    """(left, right) of a margin or padding shorthand."""
    parts = value.split()
    return (parts[3], parts[1]) if len(parts) == 4 else (parts[min(1, len(parts) - 1)],) * 2


def room(css, e, width):
    """The width e's text can take in this window: the window, no wider than any max-width on the way down, less the
    margins and padding of every element e sits in and of e itself."""
    space = float(width)
    for el in reversed(ancestry(e)):
        style = style_of(css, el, width)
        if FIXED.fullmatch(style.get("max-width", "none").strip()):
            space = min(space, px(style["max-width"].strip(), width))
        for prop in ("margin", "padding"):
            if prop in style:
                space -= sum(length(v, width) for v in sides(style[prop]))
    return space


class Story1666AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.body = self.page.find("body")[0]

    # The heading, the notice, and the rest of the page: the Given of every line.

    def heading(self):
        headings = self.page.find("h1")
        self.assertTrue(headings, "the home page has a heading")
        return headings[0]

    def notice(self):
        """The innermost element whose words say weekend workshops are full; the first, if there is more than one."""
        found = [e for e in self.page.elements if inside(e, self.body) and NOTICE.search(words(e))]
        innermost = [e for e in found if not any(inside(other, e) for other in found)]
        self.assertTrue(innermost, "the home page shows words that say weekend workshops are full")
        return innermost[0]

    def rest_of_page(self, notice):
        """What a customer sees and uses besides the notice: each region in <body>, and each heading, photo, text,
        link, and control. A pane that a button keeps closed until it is opened (aria-controls, hidden) is left out:
        it was closed before the notice too."""
        named = {b.attrs.get("aria-controls") for b in self.page.find("button")} - {None}
        left_out = [e for e in self.page.elements if e.attrs.get("id") in named and "hidden" in e.attrs] + [notice]

        def kept(e):
            return (inside(e, self.body) and e.tag not in ("script", "template")
                    and not any(x is e or inside(e, x) for x in left_out))

        return [e for e in self.page.elements
                if kept(e) and (e.parent is self.body or e.tag in SHOWN or (e.tag == "a" and e.attrs.get("href")))]

    # Shared Then checks. Each returns what is wrong, so an empty list is a pass.

    def hidden_by(self, e, width):
        """Why e cannot be seen or selected in this window: an attribute or a rule on it or on an element it sits in."""
        found = []
        for el in ancestry(e):
            found += [f"{describe(el)} is {a}" for a in ("hidden", "inert") if a in el.attrs]
            style = style_of(self.css, el, width)
            found += [f"{describe(el)} has {p}: {bad} at {width}px" for p, bad in HIDES if style.get(p, "").strip() == bad]
        return found

    def not_under(self, heading, notice, width):
        """Why the notice would not show directly under the heading in this window: it must come straight after the
        heading in the same parent, that parent must stack its children top to bottom, and neither may be moved out of
        that order."""
        parent = heading.parent
        if notice.parent is not parent:
            return [f"the notice sits in {describe(notice.parent)}, not beside the heading in {describe(parent)}"]
        siblings = [e for e in self.page.elements if e.parent is parent]
        after = siblings[siblings.index(heading) + 1:]
        found = [] if after and after[0] is notice else [f"{describe(after[0]) if after else 'nothing'} comes straight after the heading"]
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
        for el in (heading, notice):
            style = style_of(self.css, el, width)
            if style.get("position", "static").strip() in ("absolute", "fixed"):
                found.append(f"{describe(el)} is taken out of the page flow at {width}px")
            found += [f"{describe(el)} has {p}: {style[p]} at {width}px" for p in ("order", "grid-row", "grid-area", "float")
                      if style.get(p, "auto").strip() not in ("0", "auto", "none")]
        return found

    def covers(self, notice, width):
        """Why the notice could lie over other content in this window: it must stay where the page flow puts it (no
        absolute, fixed, or sticky position, offset, negative margin, or transform), and nothing it sits in may have a
        set height, so the line it adds makes the banner taller instead of spilling over what follows."""
        style = style_of(self.css, notice, width)
        found = []
        place = style.get("position", "static").strip()
        if place not in ("static", "relative"):
            found.append(f"position: {place}")
        if place == "relative":
            found += [f"{p}: {style[p]}" for p in ("top", "right", "bottom", "left", "inset")
                      if style.get(p, "auto").strip() not in ("0", "auto")]
        found += [f"{p}: {v}" for p, v in style.items() if p.startswith("margin") and re.search(r"(^|\s)-\d", v)]
        found += [f"{p}: {style[p]}" for p in ("transform", "translate") if style.get(p, "none").strip() != "none"]
        for el in ancestry(notice)[1:]:
            found += [f"{describe(el)} has {p}: {v}" for p, v in style_of(self.css, el, width).items()
                      if p in ("height", "max-height") and v.strip() not in ("auto", "none")]
        return [f"{f} at {width}px" for f in found]

    def unwrapped(self, notice, width):
        """Why the notice's words would not wrap to the window or would be cut off: white-space that holds them on one
        line, a width wider than the room its parent leaves, or a set height on it."""
        style = style_of(self.css, notice, width)
        found = []
        spacing = inherited(self.css, notice, "white-space", width, "light", "normal")
        if spacing in ("nowrap", "pre"):
            found.append(f"white-space: {spacing}")
        space = room(self.css, notice.parent, width)
        for prop in ("width", "min-width"):
            value = style.get(prop, "auto").strip()
            if FIXED.fullmatch(value) and px(value, width) > space:
                found.append(f"{prop}: {value} in {space:.0f}px")
        found += [f"{p}: {style[p]}" for p in ("height", "max-height") if style.get(p, "auto").strip() not in ("auto", "none")]
        return [f"{f} at {width}px" for f in found]

    def not_working(self, e, stops, scripts):
        """Why a link or control would not work: not a Tab stop, disabled, a link that goes nowhere, or a button outside
        a form that no script listens to."""
        found = [] if any(s is e for s in stops) else ["cannot be reached from the keyboard"]
        if {"disabled", "aria-disabled"} & e.attrs.keys():
            found.append("is disabled")
        if e.tag == "a":
            found += [p for p in [link_problem(self.page, e.attrs["href"])] if p]
        elif e.tag == "button" and not any(el.tag == "form" for el in ancestry(e)):
            names = [rf"""["']\.{re.escape(c)}["']""" for c in classes(e)]
            if e.attrs.get("id"):
                names += [rf"""["']#{re.escape(e.attrs["id"])}["']""", rf"""getElementById\(\s*["']{re.escape(e.attrs["id"])}["']"""]
            if not any(re.search(r"""addEventListener\(\s*["']click["']""", code) and any(re.search(n, code) for n in names)
                       for code in scripts):
                found.append("no script listens for a click on it")
        return found

    def test_tc1670_ac1_a_one_line_notice_that_weekend_workshops_are_full_appears_directly_under_the_heading(self):
        """AC1, Test Case 1670. Static: the notice's words and place in index.html, and the stylesheet at each width.
        Not run: the page drawn in a browser."""
        # Given a customer opens the home page.
        heading = self.heading()
        # When the page loads, in a wide window (Test Case step 1) or a narrow window (step 2).
        notice = self.notice()
        # Then a notice that weekend workshops are full appears directly under the heading.
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                self.assertEqual(self.hidden_by(heading, width), [], "the heading shows")
                self.assertEqual(self.hidden_by(notice, width), [], "the notice shows")
                self.assertEqual(self.not_under(heading, notice, width), [])
        # And it is one line: nothing inside it starts a new line, and its words fit the wide window's banner on one line.
        breaks = [describe(e) for e in self.page.elements if inside(e, notice) and e.tag in LINE_BREAKS]
        self.assertEqual(breaks, [], "nothing inside the notice starts a new line")
        size = px(inherited(self.css, notice, "font-size", WIDE, "light", f"{REM}px"), WIDE)
        needed, space = len(words(notice)) * LETTER * size, room(self.css, notice, WIDE)
        self.assertLessEqual(needed, space, f"about {needed:.0f}px of words in a {space:.0f}px line in a wide window")

    def test_tc1671_ac2_with_the_notice_shown_shop_now_works_as_before_in_wide_and_narrow_windows(self):
        """AC2, Test Case 1671. Static: Shop now's address and target, the scripts, and the stylesheet at each width.
        Not run: a real click or key press, or the scroll it causes."""
        # Given the notice is shown on the home page.
        notice = self.notice()
        shop_now = [a for a in self.page.find("a") if words(a) == "Shop now"]
        self.assertEqual(len(shop_now), 1, "the home page has one Shop now")
        shop_now = shop_now[0]
        # When the customer selects Shop now: it can be reached with Tab and pressed, and is not disabled.
        self.assertTrue(any(s is shop_now for s in tab_stops(self.page)), "Shop now can be reached from the keyboard")
        self.assertFalse({"disabled", "aria-disabled"} & shop_now.attrs.keys(), "Shop now is not disabled")
        self.assertEqual(script_problems(self.page), [], "no script stops the link or sends the customer elsewhere")
        # Then Shop now works as it did before the notice was added: it leads to the products section on this page,
        # which takes focus without becoming a Tab stop.
        href = shop_now.attrs.get("href", "").strip()
        self.assertTrue(href.startswith("#"), "Shop now stays on this page")
        self.assertIsNone(link_problem(self.page, href), href)
        target = next(e for e in self.page.elements if e.attrs.get("id") == href[1:])
        self.assertIn("products", classes(target), "Shop now still leads to the products section")
        self.assertEqual(target.attrs.get("tabindex"), "-1", "the products section takes focus without becoming a Tab stop")
        # The same in a wide window (Test Case step 1) and a narrow window (step 2): the notice shows, Shop now shows
        # and can be selected, the notice cannot lie over it, and the products section shows.
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                self.assertEqual(self.hidden_by(notice, width), [], "the notice is shown")
                self.assertEqual(self.hidden_by(shop_now, width), [], "Shop now shows and can be selected")
                self.assertEqual(self.covers(notice, width), [], "the notice cannot lie over Shop now")
                self.assertEqual(self.hidden_by(target, width), [], "the products section shows")

    def test_tc1672_ac3_the_notice_reads_under_the_heading_and_the_rest_of_the_page_shows_and_works_in_wide_and_narrow_windows(self):
        """AC3, Test Case 1672. Static: contrast, size, wrapping, and position from the stylesheet at each width, and
        every other link and control's target and wiring. Not run: a browser render, scrolling, real clicks, or Tab."""
        # Given the home page shows the notice.
        heading, notice = self.heading(), self.notice()
        rest = self.rest_of_page(notice)
        uses = [e for e in rest if (e.tag == "a" and e.attrs.get("href")) or e.tag in CONTROLS]
        self.assertTrue(uses, "the rest of the home page has links and controls")
        stops, scripts = tab_stops(self.page), [code for _, code in page_scripts(self.page)]
        self.assertEqual(script_problems(self.page), [], "no script stops a link")
        # When it is viewed in a wide window (Test Case step 1) and in a narrow window (step 2).
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                # Then the notice is readable under the heading: it shows directly under it, its words keep body-text
                # contrast in either theme and body-text size, they wrap to the window, and nothing cuts them off.
                self.assertEqual(self.hidden_by(notice, width), [], "the notice shows")
                self.assertEqual(self.not_under(heading, notice, width), [])
                for theme in THEMES:
                    colour = inherited(self.css, notice, "color", width, theme, "#000")
                    self.assertGreaterEqual(contrast(colour, backdrop(self.css, notice, width, theme)), TEXT_CONTRAST,
                                            f"the notice's words in the {theme} theme")
                size = px(inherited(self.css, notice, "font-size", width, "light", f"{REM}px"), width)
                self.assertGreaterEqual(size, READABLE, "the notice's words are at least body-text size")
                self.assertEqual(self.unwrapped(notice, width), [], "the notice wraps to the window")
                # Test Case step 2: the notice does not cover other content.
                self.assertEqual(self.covers(notice, width), [], "the notice does not cover other content")
                # And the rest of the page shows and works as before: each region, heading, photo, text, link, and
                # control shows, and each link and control can be reached from the keyboard and goes somewhere or is
                # wired to a script.
                for e in rest:
                    self.assertEqual(self.hidden_by(e, width), [], describe(e))
                for e in uses:
                    self.assertEqual(self.not_working(e, stops, scripts), [], f"{describe(e)} {words(e)}")


if __name__ == "__main__":
    unittest.main()
