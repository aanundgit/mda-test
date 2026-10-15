"""Story 1654: one test per acceptance line, named after its Test Case so the pipeline can post each result.

Every check here is static. The stack has no browser and no JavaScript runtime, so nothing clicks, presses Tab,
scrolls, or draws the page.
- index.html is read with html.parser: the button that names the pane (aria-controls), the pane, its links, and
  the sections they point at.
- The script that wires that button is read as text. Its click handler becomes a small model of what one click does
  to the button's aria-expanded and the pane's hidden attribute, and each test opens or closes the pane by applying
  that model. The model is built only when the handler has the shape the model reads (a flag from aria-expanded,
  written back to aria-expanded and, negated, to hidden). A rewrite that keeps the behaviour in another shape fails
  here, and this reader needs updating with it.
- style.css is read the way a browser applies it at a window width (1280px wide, 375px narrow). While the pane is
  open, the rules keyed to it (a :has() that holds the pane with :not([hidden])) are added.
Not checked at runtime: a real click or key press, where focus lands, the scroll after a section link, the drawn
layout (overlap and wrapping as rendered), and what a screen reader announces.
"""
import re
import unittest
from dataclasses import dataclass
from typing import Callable

from test_page import (CARD_MIN, LINK_BLUE, ROOT, WIDTH_CHECK, Element, Page, blocks, container_style, contrast,
                       position, px, read, style_at, tab_stops)
from test_story_1453_acceptance import READABLE, columns
from test_story_1459_acceptance import over_white
from test_story_1641_acceptance import NARROW, TEXT_CONTRAST, VISITED, WIDE, braced

WINDOWS = {"wide": WIDE, "narrow": NARROW}
CONTROLS = ("button", "input", "select", "textarea")
HIDES = (("display", "none"), ("visibility", "hidden"), ("pointer-events", "none"))
STOPS_A_LINK = re.compile(r"preventDefault|return\s+false")
TAKES_A_CONTROL_AWAY = re.compile(r"""\.inert\b|\.disabled\s*=|["'](?:inert|disabled|aria-hidden)["']""")
WRITES = re.compile(r"\.(?:set|remove|toggle)Attribute\(|\.(?:hidden|inert|disabled)\s*=|classList\.|\.style\.")
TEXT = (".site-name", ".offer", "h1", "h2", ".product-card h3", ".product-card p", ".shop-now", ".contact")


def classes(e):
    return (e.attrs.get("class") or "").split()


def selectors(e):
    """The simple selectors that match e: its tag, each of its classes, and its id."""
    return [e.tag, *(f".{c}" for c in classes(e)), *([f"#{e.attrs['id']}"] if e.attrs.get("id") else [])]


def ancestry(e):
    """e and each element it sits in, up to and including <body>."""
    chain = []
    while e is not None and e.tag != "html":
        chain.append(e)
        e = e.parent
    return chain


def inside(e, ancestor):
    return any(a is ancestor for a in ancestry(e)[1:])


def describe(e):
    return f"<{e.tag} {e.attrs['class']}>" if e.attrs.get("class") else f"<{e.tag}>"


def page_scripts(page):
    """(script element, the code it runs) for inline scripts and for script files in this repo loaded by src."""
    found = []
    for script in page.find("script"):
        src = (script.attrs.get("src") or "").strip()
        path = (ROOT / src).resolve()
        if not src:
            found.append((script, script.text))
        elif not re.match(r"(?i)[a-z][a-z\d+.-]*:|//", src) and path.is_relative_to(ROOT) and path.is_file():
            found.append((script, path.read_text(encoding="utf-8")))
    return found


def main_sections(page):
    """The regions a customer scrolls through below the header: each section or footer directly in <body> or <main>."""
    return [e for e in page.elements
            if e.tag in ("section", "footer") and e.parent is not None and e.parent.tag in ("body", "main")]


def link_problem(page, href):
    """Why a link with this address would go nowhere, or None when it goes somewhere."""
    href = href.strip()
    if href.startswith("#"):
        count = sum(1 for e in page.elements if e.attrs.get("id") == href[1:])
        return None if count == 1 else f"{href} names {count} elements on the page"
    if re.match(r"(?i)https?://[^/\s]+|//[^/\s]+|(mailto|tel):\S", href):
        return None
    if re.match(r"(?i)[a-z][a-z\d+.-]*:", href):
        return f"{href} is not a web address"
    path = re.split(r"[?#]", href)[0]
    return None if path and (ROOT / path).is_file() else f"{href} is not a file in this repo"


def open_rules(css, pane):
    """{selector: what it styles} for each rule that applies only while the pane is shown: a :has() holding the
    pane's class or id with :not([hidden]). body:has(...) styles body; body:has(...) main styles main."""
    names = [f".{c}" for c in classes(pane)] + ([f"#{pane.attrs['id']}"] if pane.attrs.get("id") else [])
    found = {}
    for prelude, body in blocks(css):
        for group, _ in blocks(body) if prelude.startswith("@") else [(prelude, body)]:
            for selector in (s.strip() for s in group.split(",")):
                match = re.fullmatch(r"([\w-]+):has\((.*)\)\s*(.*)", selector, re.S)
                if match and ":not([hidden])" in match.group(2) and any(n in match.group(2) for n in names):
                    found[selector] = match.group(3).strip() or match.group(1)
    return found


@dataclass
class Toggle:
    button: Element
    pane: Element
    handler: str  # The body of the button's click handler.
    flag: str  # The handler's variable for the pane's new open state.
    loaded: tuple  # (aria-expanded, hidden) as the page loads.
    click: Callable  # (aria-expanded, hidden) before one click on the button -> after it.


class Story1654AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.pane, self.open = None, {}

    # The button, the pane, and what a click does: the Given of every line.

    def toggle(self):
        navs = {n.attrs["id"]: n for n in self.page.find("nav") if n.attrs.get("id")}
        openers = [b for b in self.page.find("button")
                   if b.attrs.get("aria-controls") in navs and not any(inside(b, n) for n in navs.values())]
        self.assertTrue(openers, "a button outside the pane names the navigation pane it opens (aria-controls)")
        button = openers[0]
        pane = navs[button.attrs["aria-controls"]]
        self.pane, self.open = pane, open_rules(self.css, pane)

        ways = [r"""querySelector\(\s*["']%s["']\s*\)""" % re.escape(f".{c}") for c in classes(button)]
        if button.attrs.get("id"):
            button_id = re.escape(button.attrs["id"])
            ways += [r"""querySelector\(\s*["']#%s["']\s*\)""" % button_id, r"""getElementById\(\s*["']%s["']\s*\)""" % button_id]
        self.assertTrue(ways, "the button has a class or an id a script can find it by")
        finds = r"(\w+)\s*=\s*document\.(?:%s)" % "|".join(ways)
        wired = []
        for script, code in page_scripts(self.page):
            for found in re.finditer(finds, code):
                listen = re.search(r"""\b%s\.addEventListener\(\s*["']click["']""" % found.group(1), code)
                if listen:
                    wired.append((script, code, found.group(1), listen))
        self.assertTrue(wired, f"a script on the page finds {describe(button)} and listens for a click on it")
        script, code, var, listen = wired[0]
        self.assertTrue(position(self.page, script) > position(self.page, pane) or "defer" in script.attrs
                        or "DOMContentLoaded" in code, "the script runs once the pane is on the page")

        pane_id = re.escape(pane.attrs["id"])
        finds_pane = (r"""(\w+)\s*=\s*document\.(?:getElementById\(\s*%s\.getAttribute\(\s*["']aria-controls["']\s*\)\s*\)"""
                      r"""|getElementById\(\s*["']%s["']\s*\)|querySelector\(\s*["']#%s["']\s*\))""") % (var, pane_id, pane_id)
        found_pane = re.search(finds_pane, code)
        self.assertIsNotNone(found_pane, "the script finds the pane the button names")
        handler = braced(code, listen.start())
        flip = re.search(r"""(\w+)\s*=\s*%s\.getAttribute\(\s*["']aria-expanded["']\s*\)\s*(===|!==)\s*["'](true|false)["']"""
                         % var, handler)
        self.assertIsNotNone(flip, "the click works out the pane's new state from aria-expanded")
        flag, op, value = flip.groups()
        self.assertRegex(handler, r"""\b%s\.setAttribute\(\s*["']aria-expanded["']\s*,\s*String\(\s*%s\s*\)\s*\)""" % (var, flag),
                         "the click writes the new state to aria-expanded")
        self.assertRegex(handler, r"""\b%s\.(?:hidden\s*=\s*!\s*%s\b|toggleAttribute\(\s*["']hidden["']\s*,\s*!\s*%s\s*\))"""
                         % (found_pane.group(1), flag, flag), "the click hides the pane exactly when the new state is closed")
        self.assertNotRegex(handler, WIDTH_CHECK, "a click does the same in a wide and a narrow window")

        def click(state):
            now_open = (state[0] == value) if op == "===" else (state[0] != value)
            return ("true" if now_open else "false", not now_open)

        return Toggle(button, pane, handler, flag, (button.attrs.get("aria-expanded"), "hidden" in pane.attrs), click)

    # Reading the stylesheet with the pane open or closed.

    def styled(self, selector, width, open_):
        applied = dict(style_at(self.css, selector, width))
        if open_:
            for rule, target in self.open.items():
                if target == selector:
                    applied.update(style_at(self.css, rule, width))
        return applied

    def element_style(self, e, width, open_, scope=()):
        applied = {}
        for selector in [*selectors(e), *(f"{s} {e.tag}" for s in scope)]:
            applied.update(self.styled(selector, width, open_))
        return applied

    def hiding(self, e, width, open_, scope=(), hides=HIDES):
        """Why e cannot be seen or selected in this window: an attribute or a rule on it or on an element it sits in."""
        found = []
        for el in ancestry(e):
            if el is self.pane and not open_:
                found.append("the pane is hidden")
            elif el is not self.pane and {"hidden", "inert"} & el.attrs.keys():
                found.append(f"{describe(el)} is hidden or inert")
            style = self.element_style(el, width, open_, scope)
            found += [f"{describe(el)} has {prop}: {bad} at {width}px" for prop, bad in hides if style.get(prop, "").strip() == bad]
        return found

    def card_width(self, width, open_):
        body = self.styled("body", width, open_)
        column = width - (px(body["grid-template-columns"].split()[0], width) if body.get("display") == "grid" else 0)
        main = self.styled("main", width, open_)
        content = min(px(main["max-width"], width), column) - 2 * px(main["padding"].split()[1], width)
        grid = dict(style_at(self.css, ".product-grid", width))
        if main.get("container-type") == "inline-size":
            grid.update(container_style(self.css, ".product-grid", content))
        count = columns(grid["grid-template-columns"])
        return (content - px(grid["gap"], width) * (count - 1)) / count

    # Shared Then checks.

    def assert_lists_the_main_sections(self, pane):
        sections = main_sections(self.page)
        self.assertTrue(sections, "the home page has sections")
        listed = {a.attrs.get("href", "").strip() for a in self.page.within(pane, "a") if a.text.strip()}
        for section in sections:
            self.assertTrue(section.attrs.get("id"), f"{describe(section)} has an id, so the pane can link to it")
            self.assertIn(f"#{section.attrs['id']}", listed, f"the pane lists {describe(section)} by name")

    def assert_the_page_shows_with_the_pane(self, width, open_):
        """The regions outside the pane show, and an open pane sits beside or above them, not on top of them."""
        body = self.page.find("body")[0]
        regions = [e for e in self.page.elements if e.parent is body and e is not self.pane and e.tag != "script"]
        for region in regions:
            self.assertEqual(self.hiding(region, width, open_), [], describe(region))
        if not open_:
            return
        pane = self.element_style(self.pane, width, True)
        self.assertNotIn(pane.get("position", "static"), ("absolute", "fixed"), "the open pane is not laid over the page")
        if self.styled("body", width, True).get("display") == "grid":
            # The header comes before the pane and spans the top row; each region after the pane takes another column.
            for region in (r for r in regions if position(self.page, r) > position(self.page, self.pane)):
                column = self.element_style(region, width, True).get("grid-column")
                self.assertTrue(column and column != pane.get("grid-column"), f"{describe(region)} is beside the pane")

    def test_tc1659_ac1_opening_the_pane_lists_the_main_sections_in_wide_and_narrow_windows(self):
        """AC1, Test Case 1659. Static: the click model, the pane's links, and the stylesheet at each width.
        Not run: a real click, or the pane as drawn."""
        # Given the home page is open, in a wide window or a narrow window.
        toggle = self.toggle()
        # When the customer opens the side navigation pane: one click on the button that names it.
        _, hidden = toggle.click(toggle.loaded)
        # Then it lists the main sections of the site: a named link to each section of the home page.
        self.assertFalse(hidden, "one click on the button shows the pane")
        self.assert_lists_the_main_sections(toggle.pane)
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                for link in self.page.within(toggle.pane, "a"):
                    self.assertEqual(self.hiding(link, width, True, scope=selectors(toggle.pane)), [], link.text.strip())
                # Test Case step 2: the open pane fits the window; no width it takes is wider than the window.
                body, pane = self.styled("body", width, True), self.element_style(toggle.pane, width, True)
                widths = [body["grid-template-columns"].split()[0]] if body.get("display") == "grid" else []
                widths += [pane[k] for k in ("width", "min-width") if k in pane]
                for value in widths:
                    self.assertLessEqual(px(value, width), width, f"the pane takes {value} in a {width}px window")
                # Test Case step 3: the rest of the page still shows.
                self.assert_the_page_shows_with_the_pane(width, open_=True)

    def test_tc1660_ac2_closing_the_open_pane_hides_it_and_the_page_shows_as_before(self):
        """AC2, Test Case 1660. Static: the click model and the pane's rules at each width.
        Not run: a real click, or the page as drawn after it."""
        toggle = self.toggle()
        # Given the side navigation pane is open.
        opened = toggle.click(toggle.loaded)
        self.assertFalse(opened[1], "one click on the button opens the pane")
        # When the customer closes it: a second click on the same button.
        closed = toggle.click(opened)
        # Then the pane hides: hidden is back on it, and no rule for the pane overrides hidden, wide or narrow.
        self.assertTrue(closed[1], "the second click sets hidden on the pane")
        for name, width in WINDOWS.items():
            with self.subTest(window=name):
                display = self.element_style(toggle.pane, width, False).get("display", "none").strip()
                self.assertEqual(display, "none", "a display rule on the closed pane would show it despite hidden")
        # And the page shows as before: the button and the pane are back as the page loaded them, and every change the
        # click makes follows the new state, so closing undoes all that opening did. The click is the same at any
        # width (checked in toggle()), so this holds in a wide and a narrow window.
        self.assertEqual(closed, toggle.loaded, "after closing, the button and pane are as the page loaded them")
        for statement in re.split(r"[;\n]", toggle.handler):
            if WRITES.search(statement):
                self.assertRegex(statement, rf"\b{toggle.flag}\b", f"follows the open state: {statement.strip()}")
        # Test Case step 3: given the pane was closed, when the customer opens it again, then it lists the sections again.
        self.assertFalse(toggle.click(closed)[1], "a third click opens the pane again")
        self.assert_lists_the_main_sections(toggle.pane)

    def test_tc1661_ac3_selecting_a_section_in_the_open_pane_moves_the_page_to_it_in_wide_and_narrow_windows(self):
        """AC3, Test Case 1661. Static: each link's target, the rules at each width, and the scripts.
        Not run: a real click, or the scroll it causes."""
        toggle = self.toggle()
        # Given the side navigation pane is open.
        self.assertFalse(toggle.click(toggle.loaded)[1], "one click on the button opens the pane")
        links = [a for a in self.page.within(toggle.pane, "a") if a.attrs.get("href", "").strip().startswith("#")]
        self.assertTrue(links, "the pane holds links to sections of this page")
        for code in (code for _, code in page_scripts(self.page)):
            self.assertNotRegex(code, STOPS_A_LINK, "no script stops a link's jump to its section")
        for name, width in WINDOWS.items():
            for link in links:
                with self.subTest(window=name, section=link.text.strip()):
                    # When the customer selects a section in it: the link shows, has a name, and can be selected.
                    self.assertTrue(link.text.strip(), "the link has a visible name")
                    self.assertEqual(self.hiding(link, width, True, scope=selectors(toggle.pane)), [])
                    self.assertNotIn(link.attrs.get("aria-disabled"), ("true",), "the link is not disabled")
                    stops = [n for el in ancestry(link) for n, v in el.attrs.items()
                             if n.startswith("on") and STOPS_A_LINK.search(v or "")]
                    self.assertEqual(stops, [], "no inline handler stops the link")
                    # Then the page moves to that section: the link names one element on this page, outside the pane,
                    # that shows in this window, so the browser's jump to it lands on the section.
                    targets = [e for e in self.page.elements if e.attrs.get("id") == link.attrs["href"].strip()[1:]]
                    self.assertEqual(len(targets), 1, f"{link.attrs['href']} names one element")
                    self.assertFalse(inside(targets[0], toggle.pane), "the link leads out of the pane into the page")
                    self.assertEqual(self.hiding(targets[0], width, True, hides=HIDES[:2]), [], "the section shows")

    def test_tc1662_ac4_with_the_pane_open_or_closed_text_stays_readable_and_every_link_and_control_works(self):
        """AC4, Test Case 1662. Static: contrast, sizes, card widths, link targets, and script wiring at each width,
        with the open pane's rules added when it is open. Not run: a browser render, real clicks, or Tab presses."""
        toggle = self.toggle()
        header = self.page.find("header")[0]
        stops = tab_stops(self.page)
        rest = [e for e in self.page.elements if (e.tag == "a" and e.attrs.get("href")) or e.tag in CONTROLS]
        rest = [e for e in rest if not inside(e, toggle.pane)]
        self.assertTrue(rest, "the rest of the home page has links and controls")
        scripts = [code for _, code in page_scripts(self.page)]
        for code in scripts:
            self.assertNotRegex(code, STOPS_A_LINK, "no script stops a link")
            self.assertNotRegex(code, TAKES_A_CONTROL_AWAY, "no script makes the page inert, disabled, or hidden")
        # Given the side navigation pane is open or closed.
        for state, (expanded, hidden) in {"closed": toggle.loaded, "open": toggle.click(toggle.loaded)}.items():
            open_ = not hidden
            # When the customer uses the rest of the home page in a wide window and a narrow window.
            for name, width in WINDOWS.items():
                with self.subTest(pane=state, window=name):
                    # Then all text stays readable: the page shows clear of the pane, its text keeps its contrast and
                    # size, long words wrap, and each product card stays wide enough to read.
                    self.assert_the_page_shows_with_the_pane(width, open_)
                    body, top = self.styled("body", width, open_), self.styled(".site-header", width, open_)
                    pairs = {"page text": (body["color"], body["background"]), "header text": (top["color"], top["background"])}
                    for button in self.page.within(header, "button"):
                        attrs = {**button.attrs, "aria-expanded": expanded} if button is toggle.button else button.attrs
                        style = self.element_style(button, width, open_)
                        for c in classes(button):
                            for attr in (a for a in attrs if a.startswith("aria-")):
                                style.update(self.styled(f'.{c}[{attr}="{attrs[attr]}"]', width, open_))
                        label, fill = style.get("color", "inherit"), style.get("background", "transparent")
                        pairs[f"{button.text.strip()} label"] = (top["color"] if label in ("inherit", "currentColor") else label,
                                                                 top["background"] if fill == "transparent" else fill)
                    if self.page.find("div", class_="banner-text"):
                        banner = self.styled(".banner-text", width, open_)
                        pairs["banner text over the brightest photo"] = (banner["color"], over_white(banner["background"]))
                    if self.page.find("a", class_="shop-now"):
                        shop = self.styled(".shop-now", width, open_)
                        pairs["Shop now label"] = (shop["color"], shop["background"])
                    if self.page.find("li", class_="product-card"):
                        card = self.styled(".product-card", width, open_)
                        pairs["card text"] = (card.get("color", body["color"]), card.get("background", body["background"]))
                    if self.page.find("a", class_="contact"):
                        contact = self.styled(".contact", width, open_)
                        for colour in [contact["color"]] if "color" in contact else [LINK_BLUE, VISITED]:
                            pairs[f"contact link {colour}"] = (colour, body["background"])
                    for what, (text, background) in pairs.items():
                        self.assertGreaterEqual(contrast(text, background), TEXT_CONTRAST, what)
                    for selector in TEXT:
                        size = self.styled(selector, width, open_).get("font-size")
                        if size:
                            self.assertGreaterEqual(px(size, width), READABLE, selector)
                    for selector in ("main", ".banner"):
                        self.assertEqual(self.styled(selector, width, open_).get("overflow-wrap"), "anywhere", selector)
                    if self.page.find("li", class_="product-card"):
                        self.assertGreaterEqual(self.card_width(width, open_), CARD_MIN, "each product card is readable")
                    # And every link and control keeps working: each shows, can be reached from the keyboard, and goes
                    # somewhere or is wired to a script.
                    for e in rest:
                        where = f"{describe(e)} {e.text.strip()}"
                        self.assertEqual(self.hiding(e, width, open_), [], where)
                        self.assertIn(e, stops, f"{where} can be reached from the keyboard")
                        self.assertFalse({"disabled", "aria-disabled"} & e.attrs.keys(), f"{where} is not disabled")
                        stoppers = [n for el in ancestry(e) for n, v in el.attrs.items()
                                    if n.startswith("on") and STOPS_A_LINK.search(v or "")]
                        self.assertEqual(stoppers, [], f"no inline handler stops {where}")
                        if e.tag == "a":
                            self.assertIsNone(link_problem(self.page, e.attrs["href"]), where)
                        elif e.tag == "button" and not any(el.tag == "form" for el in ancestry(e)):
                            names = [rf"""["']\.{re.escape(c)}["']""" for c in classes(e)]
                            if e.attrs.get("id"):
                                names += [rf"""["']#{re.escape(e.attrs["id"])}["']""",
                                          rf"""getElementById\(\s*["']{re.escape(e.attrs["id"])}["']"""]
                            wired = [code for code in scripts if re.search(r"""addEventListener\(\s*["']click["']""", code)
                                     and any(re.search(n, code) for n in names)]
                            self.assertTrue(wired, f"a script listens for a click on {where}")


if __name__ == "__main__":
    unittest.main()
