"""Story 1641: one test per acceptance line, named after its Test Case so the pipeline can post each result.

The stack has no browser and no JavaScript runtime, so nothing here clicks the button or reopens the page.
Window widths are checked by reading the stylesheet the way a browser applies it at that width, a theme by
adding the [data-theme="dark"] rules on top, and theme.js by reading it as text: which function reads and
saves the choice, which one sets data-theme, and where each is called.
"""
import re
import unittest

from test_page import (DARK, LINK_BLUE, Page, blocks, contrast, luminance, read, script_problems, style_at, tab_stops,
                       themed)
from test_story_1453_acceptance import columns
from test_story_1459_acceptance import over_white

WIDE, NARROW = 1280, 375
TEXT_CONTRAST = 4.5  # WCAG AA for body-size text.
OUTLINE_CONTRAST = 3  # WCAG AA for a focus indicator against what is next to it.
VISITED = "#551a8b"  # A browser's default visited-link colour, used where the stylesheet sets none.
COLOUR_ONLY = {"color", "color-scheme", "background", "background-color", "border-color", "border-top-color", "outline-color"}
WIDTH_CHECK = r"matchMedia|innerWidth|outerWidth|clientWidth|\bscreen\."


def braced(text, start):
    """The text inside the first {...} at or after start, nested braces included."""
    opening, depth = text.index("{", start), 0
    for i in range(opening, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[opening + 1:i]
    raise ValueError("unbalanced braces")


def handler(script, event):
    """The body of the function the script passes to addEventListener for event."""
    return braced(script, script.index(f'addEventListener("{event}"'))


def functions(script):
    """Each named function the script declares, as {name: body}."""
    return {m.group(1): braced(script, m.end() - 1) for m in re.finditer(r"function\s+(\w+)\s*\([^)]*\)\s*\{", script)}


def dark_rules(css):
    """(selectors, declarations) for every rule that applies only under [data-theme="dark"], @media rules included."""
    found = []
    for prelude, body in blocks(css):
        for selectors, declarations in blocks(body) if prelude.startswith("@media") else [(prelude, body)]:
            if DARK in selectors:
                found.append((selectors, declarations))
    return found


class Story1641AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.header = self.page.find("header")[0]

    def theme_button(self):
        buttons = [b for b in self.page.within(self.header, "button")
                   if re.search(r"(?i)\b(theme|dark|light)\b", b.text + " " + (b.attrs.get("aria-label") or ""))]
        self.assertEqual(len(buttons), 1, "the header holds one button whose label names the theme")
        return buttons[0]

    def theme_script(self):
        head = self.page.find("head")[0]
        scripts = [s for s in self.page.within(head, "script") if s.attrs.get("src") == "theme.js"]
        self.assertEqual(len(scripts), 1, "index.html loads theme.js from <head>")
        return scripts[0], read("theme.js")

    def the_one(self, found, what):
        """The name of the one function whose body holds what."""
        names = [name for name, body in found.items() if what in body]
        self.assertEqual(len(names), 1, f"one function holds {what}")
        return names[0]

    def assert_light_and_dark_at(self, width):
        for selector in ("body", ".product-card"):
            self.assertGreater(luminance(themed(self.css, selector, width, "light")["background"]), 0.5,
                               f"{selector} is light in the light theme at {width}px")
            self.assertLess(luminance(themed(self.css, selector, width, "dark")["background"]), 0.05,
                            f"{selector} is dark in the dark theme at {width}px")

    def test_tc1647_ac1_the_theme_button_shows_in_the_header_and_can_be_selected_in_wide_and_narrow_windows(self):
        """AC1, Test Case 1647."""
        # Given a customer opens the home page.
        button = self.theme_button()
        # When the page loads in a wide window or a narrow window.
        for width in (WIDE, NARROW):
            header, style = style_at(self.css, ".site-header", width), style_at(self.css, ".theme-toggle", width)
            # Then a theme button is shown in the header, and it can be selected.
            self.assertFalse({"hidden", "aria-hidden", "disabled", "aria-disabled"} & button.attrs.keys())
            self.assertNotEqual(style.get("display"), "none", f"shown at {width}px")
            self.assertNotEqual(style.get("visibility"), "hidden", f"shown at {width}px")
            self.assertNotEqual(style.get("pointer-events"), "none", f"can be selected at {width}px")
            self.assertLessEqual(int(style["grid-column"].split("/")[0]), columns(header["grid-template-columns"]),
                                 f"the button sits in a column the header has at {width}px, not one past its edge")
        self.assertIn(button, tab_stops(self.page), "the button can be reached and selected from the keyboard")
        # The rest of the page shows and works as before: the header text, banner, products, footer, and its links.
        self.assertEqual([p.attrs.get("class") for p in self.page.within(self.header, "p")], ["site-name", "offer"])
        order = [e.attrs.get("class") or e.tag for e in self.page.elements if e.tag in ("header", "section", "main", "footer")]
        self.assertEqual(order, ["site-header", "banner", "main", "products", "site-footer"])
        # Later stories add Tab stops of their own (story 1654's Sections button and section links), so the theme
        # button, Shop now, and the contact link are checked once each, in order, not as the only Tab stops.
        own = [e.attrs.get("class") for e in tab_stops(self.page) if e.attrs.get("class") in ("theme-toggle", "shop-now", "contact")]
        self.assertEqual(own, ["theme-toggle", "shop-now", "contact"])

    def test_tc1648_ac2_selecting_the_theme_button_switches_light_to_dark_and_back_in_wide_and_narrow_windows(self):
        """AC2, Test Case 1648. Static: the click wiring and the dark rules. Not run: a real click in a browser."""
        # Given the home page shows the light theme.
        button = self.theme_button()
        self.assertNotEqual(self.page.find("html")[0].attrs.get("data-theme"), "dark", "the page source opens light")
        self.assertEqual(button.attrs.get("aria-pressed"), "false", "the button starts unpressed")
        # When the customer selects the theme button: theme.js listens for a click on that button.
        _, script = self.theme_script()
        self.assertIn(f'querySelector(".{button.attrs["class"]}")', script)
        click, found = handler(script, "click"), functions(script)
        apply = self.the_one(found, 'setAttribute("data-theme"')
        root = re.search(r"(\w+)\s*=\s*document\.documentElement\b", script).group(1)
        # Then the click flips data-theme on <html>, dark to light and anything else to dark, and aria-pressed follows.
        flip = re.search(rf'(\w+)\s*=\s*{root}\.getAttribute\("data-theme"\)\s*===\s*"dark"\s*\?\s*"light"\s*:\s*"dark"',
                         click)
        self.assertIsNotNone(flip, "selecting the button picks the other theme")
        self.assertRegex(click, rf"\b{apply}\({flip.group(1)}\)", "and applies it straight away")
        self.assertIn(f'{root}.setAttribute("data-theme"', found[apply])
        self.assertRegex(found[apply], r'setAttribute\("aria-pressed",\s*String\(\w+\s*===\s*"dark"\)\)')
        # The stylesheet turns the site dark under data-theme="dark" and back to light under anything else,
        # the same way in a wide and a narrow window.
        self.assertEqual(set(re.findall(r'\[data-theme(?:="([^"]*)")?\]', self.css)), {"dark"},
                         "only dark has its own rules, so data-theme light falls back to the light page")
        self.assertNotIn("prefers-color-scheme", self.css, "the system setting does not override the customer's choice")
        self.assertNotRegex(script, WIDTH_CHECK, "the switch works the same at any width")
        for width in (WIDE, NARROW):
            self.assert_light_and_dark_at(width)

    def test_tc1649_ac3_the_chosen_theme_is_saved_and_applied_before_the_page_draws_on_the_next_visit(self):
        """AC3, Test Case 1649. Static: what theme.js saves, reads, and applies, and where. Not run: a real reopen."""
        # Given the customer chose a theme: the click saves the same theme it applies, light as well as dark.
        tag, script = self.theme_script()
        found, click, ready = functions(script), handler(script, "click"), handler(script, "DOMContentLoaded")
        save, load = self.the_one(found, "localStorage.setItem"), self.the_one(found, "localStorage.getItem")
        apply = self.the_one(found, 'setAttribute("data-theme"')
        chosen = re.search(rf"\b{apply}\((\w+)\)", click).group(1)
        self.assertRegex(click, rf"\b{save}\({chosen}\)", "the theme the customer switched to is the one saved")
        self.assertNotIn("sessionStorage", script, "the choice outlives closing the site")
        key = re.search(r"localStorage\.setItem\((\w+),", found[save]).group(1)
        self.assertRegex(found[load], rf"localStorage\.getItem\({key}\)", "the choice is read back under its own key")
        # When they close the site and open the home page again: theme.js runs from <head>, before <body> is drawn.
        self.assertFalse({"defer", "async"} & tag.attrs.keys(), "the script runs before the first paint")
        self.assertIn(tag.attrs.get("type", "text/javascript"), ("text/javascript", ""), "a module script is deferred")
        # Then the home page opens in the theme they chose: the saved theme is applied at the top of the script,
        # outside every function and the ready handler. A saved dark opens dark; light, nothing, or blocked storage
        # opens light.
        top = script
        for body in [*found.values(), ready]:
            top = top.replace(body, "")
        self.assertRegex(top, rf"\b{apply}\(\s*{load}\(\)\s*\)", "the saved theme is set on <html> as the script loads")
        self.assertRegex(found[load], rf'getItem\({key}\)\s*===\s*"dark"\s*\?\s*"dark"\s*:\s*"light"')
        self.assertRegex(ready, rf"\b{apply}\(", "the button shows pressed when the page opens dark")
        # The same in a narrow window: nothing in the script depends on width, and the dark rules apply there too.
        self.assertNotRegex(script, WIDTH_CHECK)
        self.assertEqual(themed(self.css, "body", NARROW, "dark")["background"],
                         themed(self.css, "body", WIDE, "dark")["background"])

    def test_tc1650_ac4_in_either_theme_and_any_width_all_text_is_readable_and_every_link_and_control_works(self):
        """AC4, Test Case 1650. Static: colours, contrast, Tab stops, and links. Not run: a browser render."""
        # Given either theme is active: the dark theme only changes colours, so layout and behaviour are the same.
        rules = dark_rules(self.css)
        self.assertTrue(rules, "the stylesheet has a dark theme")
        for selectors, declarations in rules:
            self.assertLessEqual(set(re.findall(r"([\w-]+)\s*:", declarations)), COLOUR_ONLY, selectors)
        # When the customer uses the rest of the home page in a wide window and a narrow window.
        for theme in ("light", "dark"):
            for width in (WIDE, NARROW):
                with self.subTest(theme=theme, width=width):
                    style = {selector: themed(self.css, selector, width, theme) for selector in (
                        "body", ".site-header", ".banner-text", ".shop-now", ".product-card", ".contact", ".theme-toggle")}
                    body, header, card = style["body"], style[".site-header"], style[".product-card"]
                    overlay = over_white(style[".banner-text"]["background"])
                    # theme.js sets aria-pressed to true in the dark theme and to false in the light one.
                    toggle = dict(style[".theme-toggle"])
                    if theme == "dark":
                        toggle.update(themed(self.css, '.theme-toggle[aria-pressed="true"]', width, theme))
                    label = header["color"] if toggle.get("color", "inherit") == "inherit" else toggle["color"]
                    fill = toggle.get("background", "transparent")
                    contact = [style[".contact"]["color"]] if "color" in style[".contact"] else [LINK_BLUE, VISITED]
                    # Then all text stays readable, section by section.
                    pairs = {
                        "header text": (header["color"], header["background"]),
                        "theme button label": (label, header["background"] if fill == "transparent" else fill),
                        "banner headline over the brightest photo": (style[".banner-text"]["color"], overlay),
                        "Shop now label": (style[".shop-now"]["color"], style[".shop-now"]["background"]),
                        "Products heading": (body["color"], body["background"]),
                        "card name and description": (card.get("color", body["color"]), card["background"]),
                        **{f"contact link {c}": (c, body["background"]) for c in contact},
                    }
                    for name, (text, background) in pairs.items():
                        self.assertGreaterEqual(contrast(text, background), TEXT_CONTRAST, name)
                    # And every control's focus outline shows against what is next to it.
                    outlines = {
                        ".theme-toggle:focus-visible": header["background"],
                        ".shop-now:focus-visible": overlay,
                        ".contact:focus-visible": body["background"],
                    }
                    for selector, background in outlines.items():
                        colour = themed(self.css, selector, width, theme)["outline"].split()[2]
                        for c in contact if colour == "currentColor" else [colour]:
                            self.assertGreaterEqual(contrast(c, background), OUTLINE_CONTRAST, selector)
        # And every link and control keeps working: the Tab stops, their targets, and no script that stops a link.
        # Later stories add Tab stops of their own (story 1654's Sections button and section links), so the theme
        # button, Shop now, and the contact link are checked once each, in order, not as the only Tab stops.
        stops = [e for e in tab_stops(self.page) if e.attrs.get("class") in ("theme-toggle", "shop-now", "contact")]
        self.assertEqual([e.attrs.get("class") for e in stops], ["theme-toggle", "shop-now", "contact"])
        target = self.page.find("section", id=stops[1].attrs["href"].lstrip("#"))
        self.assertEqual([t.attrs.get("class") for t in target], ["products"], "Shop now still leads to the products")
        self.assertRegex(stops[2].attrs["href"], r"^https?://", "the contact link still goes to a web address")
        self.assertEqual(script_problems(self.page), [], "no script can stop a link")


if __name__ == "__main__":
    unittest.main()
