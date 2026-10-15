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


def tab_stops(page):
    """The elements Tab visits, in page order. A negative tabindex can take focus but is never a Tab stop."""
    def stop(e):
        index = e.attrs.get("tabindex")
        if index is not None:
            return not index.startswith("-")
        return (e.tag == "a" and e.attrs.get("href")) or e.tag in ("input", "button", "select", "textarea")
    return [e for e in page.elements if stop(e)]


SIGN_IN_PAYMENT_OR_SEARCH = re.compile(
    r"(?i)(?<![a-z])(sign[\s_-]?(in|on)|log[\s_-]?(in|on)|password|pay(ment)?|checkout|check[\s_-]out|carts?|search)(?![a-z])")
LABELLED = ("a", "button", "input", "select", "textarea", "label")


def sign_in_payment_or_search_controls(page):
    """Forms, search areas, password, search, and payment fields, and any control or link whose label, name, or
    target is sign in, log in, password, pay, checkout, cart, or search. Other buttons and links are allowed."""
    def blocked(e):
        if e.tag in ("form", "search") or e.attrs.get("role") in ("search", "searchbox"):
            return True
        kind, autocomplete = (e.attrs.get(name) or "" for name in ("type", "autocomplete"))
        if e.tag == "input" and (kind.lower() in ("password", "search") or re.search(r"(?i)cc-|password", autocomplete)):
            return True
        if e.tag in LABELLED or e.attrs.get("role") in ("button", "link"):
            names = ("aria-label", "title", "value", "placeholder", "name", "id", "class", "href", "formaction")
            return bool(SIGN_IN_PAYMENT_OR_SEARCH.search(" ".join([e.text, *(e.attrs.get(n) or "" for n in names)])))
        return False
    return [e for e in page.elements if blocked(e)]


SCRIPT_CAN_LEAVE_OR_STOP_A_LINK = re.compile(r"\blocation\b|\bnavigate\b|\bopen\s*\(|\bwrite(ln)?\s*\(|preventDefault|return\s+false")


def script_problems(page):
    """Scripts that could send the customer to a sign-in page or stop a link. Only a script file in this repo,
    loaded by src, is allowed, and it must not touch location, navigate, open a window, write the page, call
    preventDefault, or return false. Inline code, an on* handler, a javascript: address, and another host fail."""
    found = []
    for e in page.elements:
        found += [f"<{e.tag} {name}>" for name in e.attrs if name.startswith("on")]
        found += [f"<{e.tag} {name}>" for name in ("href", "src", "action", "formaction")
                  if (e.attrs.get(name) or "").strip().lower().startswith("javascript:")]
    for script in page.find("script"):
        src = (script.attrs.get("src") or "").strip()
        path = (ROOT / src).resolve()
        if not src or script.text.strip():
            found.append("inline script")
        elif re.match(r"(?i)[a-z][a-z\d+.-]*:|//", src) or not path.is_relative_to(ROOT) or not path.is_file():
            found.append(f"{src}: not a file in this repo")
        elif SCRIPT_CAN_LEAVE_OR_STOP_A_LINK.search(path.read_text(encoding="utf-8")):
            found.append(f"{src}: can change the address or stop a link")
    return found


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


def luminance(colour):
    """WCAG relative luminance of #rgb, #rrggbb, or an (r, g, b) tuple of 0-255 channels."""
    if isinstance(colour, str):
        digits = colour.lstrip("#")
        if len(digits) == 3:
            digits = "".join(d * 2 for d in digits)
        colour = [int(digits[i:i + 2], 16) for i in (0, 2, 4)]
    linear = [c / 255 / 12.92 if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in colour]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a, b):
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


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

    def test_the_banner_headline_is_the_only_main_heading(self):
        self.assertEqual(len(self.page.find("h1")), 1)
        self.assertEqual(self.text("h1"), "Gear up for your next trail")

    def test_the_page_title_is_the_site_name(self):
        self.assertEqual(self.text("title"), self.text("p", class_="site-name"))

    def test_the_header_holds_the_site_name_and_offer_line_and_the_footer_holds_the_contact_link(self):
        header, footer = self.page.find("header")[0], self.page.find("footer")[0]
        self.assertEqual([e.attrs.get("class") for e in self.page.within(header, "p")], ["site-name", "offer"])
        self.assertEqual(self.text("p", class_="site-name"), "Northwind Outdoor")
        self.assertEqual([e.attrs.get("class") for e in self.page.within(footer, "a")], ["contact"])

    def test_the_contact_link_goes_to_a_web_address(self):
        self.assertRegex(self.page.find("a", class_="contact")[0].attrs["href"], r"^https?://")

    def test_the_page_has_no_sign_in_payment_or_search_control(self):
        self.assertEqual(sign_in_payment_or_search_controls(self.page), [])


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


class BannerTests(unittest.TestCase):
    def setUp(self):
        self.page = Page(read("index.html"))
        self.banner = self.page.find("section", class_="banner")[0]

    def test_the_banner_comes_straight_after_the_header_and_before_main(self):
        order = [e for e in self.page.elements if e.tag in ("header", "main") or e is self.banner]
        self.assertEqual([e.tag for e in order], ["header", "section", "main"])

    def test_the_banner_is_labelled_by_its_headline(self):
        heading = self.page.find("h1", id=self.banner.attrs["aria-labelledby"])[0]
        self.assertIn(heading, self.page.within(self.banner, "h1"))

    def test_the_banner_holds_one_described_photo(self):
        photos = self.page.within(self.banner, "img")
        self.assertEqual(len(photos), 1)
        self.assertGreaterEqual(len(photos[0].attrs.get("alt", "").split()), 4)

    def test_shop_now_links_to_the_products_section(self):
        links = self.page.within(self.banner, "a")
        self.assertEqual([(a.attrs.get("class"), a.text.strip()) for a in links], [("shop-now", "Shop now")])
        target = links[0].attrs["href"]
        self.assertEqual(self.page.find("section", id=target.lstrip("#"))[0].attrs.get("class"), "products")

    def test_the_products_section_can_take_focus_without_becoming_a_tab_stop(self):
        self.assertEqual(self.page.find("section", class_="products")[0].attrs.get("tabindex"), "-1")


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

    def test_the_banner_photo_and_text_share_one_grid_cell(self):
        self.assertEqual(style_at(self.css, ".banner", 1280)["display"], "grid")
        self.assertEqual(style_at(self.css, ".banner > *", 1280)["grid-area"], "1 / 1")

    def test_the_banner_photo_covers_the_banner_without_stretching(self):
        photo = style_at(self.css, ".banner-photo", 1280)
        self.assertEqual((photo["width"], photo["height"], photo["object-fit"]), ("100%", "100%", "cover"))

    def test_the_banner_text_sits_on_a_dark_overlay(self):
        self.assertRegex(style_at(self.css, ".banner-text", 1280)["background"], r"rgb\(0 0 0 / 0\.\d+\)")

    def test_shop_now_shows_a_visible_focus_outline(self):
        self.assertRegex(self.css, r"\.shop-now:focus-visible\s*\{[^}]*outline:\s*\d+px solid")


DARK = '[data-theme="dark"]'
LINK_BLUE = "#0000ee"  # A browser's default link colour, used where the stylesheet sets none.


def themed(css, selector, width, theme):
    """The declarations selector gets in that theme. A dark rule repeats the selector after [data-theme="dark"]."""
    applied = style_at(css, selector, width)
    if theme == "dark":
        applied.update(style_at(css, f"{DARK} {selector}", width))
    return applied


class ThemeTests(unittest.TestCase):
    """Story 1641: a theme button in the header switches the site between light and dark and keeps the choice."""

    WIDE, NARROW = 1280, 375

    def setUp(self):
        self.page = Page(read("index.html"))
        self.css = read("style.css")
        self.header = self.page.find("header")[0]

    def test_the_header_holds_one_theme_button_that_starts_unpressed(self):
        buttons = self.page.within(self.header, "button")
        self.assertEqual([b.attrs.get("class") for b in buttons], ["theme-toggle"])
        self.assertEqual(buttons[0].attrs.get("type"), "button", "the button submits nothing")
        self.assertEqual(buttons[0].attrs.get("aria-pressed"), "false", "the page starts in the light theme")
        self.assertTrue(buttons[0].text.strip(), "the button has a visible label")

    def test_the_theme_script_loads_in_the_head_before_the_page_is_drawn(self):
        scripts = self.page.within(self.page.find("head")[0], "script")
        self.assertEqual([s.attrs.get("src") for s in scripts], ["theme.js"])
        self.assertFalse({"defer", "async"} & scripts[0].attrs.keys(), "a saved dark theme applies before the first paint")
        self.assertEqual(script_problems(self.page), [])

    def test_the_theme_script_saves_the_choice_and_opens_light_when_storage_is_blocked(self):
        script = read("theme.js")
        for call in ("localStorage.getItem", "localStorage.setItem", 'addEventListener("click"', '"aria-pressed"'):
            self.assertIn(call, script)
        self.assertEqual(script.count("try {"), 2, "reading and saving the choice each survive blocked storage")
        self.assertRegex(script, r'catch \(error\) \{\s*return "light";', "blocked storage opens the light theme")

    def test_the_dark_theme_darkens_the_page_and_the_cards_and_tells_the_browser(self):
        self.assertGreater(luminance(themed(self.css, "body", self.WIDE, "light")["background"]), 0.9)
        for selector in ("body", ".product-card"):
            self.assertLess(luminance(themed(self.css, selector, self.WIDE, "dark")["background"]), 0.05, selector)
        self.assertEqual(style_at(self.css, DARK, self.WIDE).get("color-scheme"), "dark", "scrollbars match the theme")

    def test_text_and_links_stay_readable_in_both_themes_in_wide_and_narrow_windows(self):
        for theme in ("light", "dark"):
            for width in (self.WIDE, self.NARROW):
                with self.subTest(theme=theme, width=width):
                    body = themed(self.css, "body", width, theme)
                    card = themed(self.css, ".product-card", width, theme)
                    header = themed(self.css, ".site-header", width, theme)
                    label = themed(self.css, ".theme-toggle", width, theme).get("color", "inherit")
                    pressed = themed(self.css, '.theme-toggle[aria-pressed="true"]', width, theme)
                    pairs = {
                        "page text": (body["color"], body["background"]),
                        "card text": (card.get("color", body["color"]), card["background"]),
                        "contact link": (themed(self.css, ".contact", width, theme).get("color", LINK_BLUE), body["background"]),
                        "header text": (header["color"], header["background"]),
                        "theme button label": (header["color"] if label == "inherit" else label, header["background"]),
                        "pressed theme button label": (pressed["color"], pressed["background"]),
                    }
                    for name, (text, background) in pairs.items():
                        self.assertGreaterEqual(contrast(text, background), 4.5, name)

    def test_the_theme_button_shows_a_visible_focus_outline_on_the_header(self):
        width, line, colour = style_at(self.css, ".theme-toggle:focus-visible", self.WIDE)["outline"].split()
        self.assertGreaterEqual(px(width, self.WIDE), 2)
        self.assertEqual(line, "solid")
        self.assertGreaterEqual(contrast(colour, style_at(self.css, ".site-header", self.WIDE)["background"]), 3)

    def test_the_theme_button_sits_beside_the_centred_header_text_when_wide_and_below_it_when_narrow(self):
        self.assertEqual(style_at(self.css, ".site-header", self.WIDE)["grid-template-columns"], "1fr auto 1fr",
                         "equal side columns keep the site name centred")
        wide = style_at(self.css, ".theme-toggle", self.WIDE)
        self.assertEqual((wide["grid-column"], wide["justify-self"]), ("3", "end"))
        self.assertEqual(style_at(self.css, ".site-header", self.NARROW)["grid-template-columns"], "minmax(0, 1fr)")
        narrow = style_at(self.css, ".theme-toggle", self.NARROW)
        self.assertEqual((narrow["grid-column"], narrow["justify-self"]), ("1", "center"))
        self.assertEqual(style_at(self.css, ".site-header > p", self.NARROW)["grid-column"], "1")


if __name__ == "__main__":
    unittest.main()
