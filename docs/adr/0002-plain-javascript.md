# 0002. Plain JavaScript for web-frontend work

Date: 2026-10-15

Status: Accepted. The signed-in person approved it for story 1641. It adds to 0001; the rest of 0001 stands.

## Context

Story 1641 adds a theme button to the home page header. It switches the site between a light and a dark theme and keeps the customer's choice for the next visit. HTML and CSS can switch a theme, but a static page cannot remember a choice without a script that writes to the browser's storage.

## Decision

This repo is a web-frontend project. Static web pages: HTML, CSS, and plain JavaScript. No build step and no packages.

| | |
|---|---|
| Language | html, css, javascript |
| Framework | none |
| Runtime | static-hosting |
| Test | `python3 -m unittest discover -s tests` |
| Build | none |
| Template | none |

## Rules for a script

- A script is a file in this repo, loaded with `<script src>`. No inline script, no `on*` handler attribute, no `javascript:` address, and no script from another host.
- The file runs in the browser as written. No package, framework, bundler, or transpiler.
- A script does not change the page address, open a window, write the page, or stop a link. `script_problems` in `tests/test_page.py` fails if it does.
- Without the script the page still reads and its links still work, in the light theme.

## Consequences

- `theme.js` is the first script. It keeps the theme in `localStorage` and opens the page in the light theme when storage is blocked or empty.
- The tests read the page with `html.parser` and read the script as text. They do not run it. The test command adds no browser and no JavaScript runtime.
- `.mda/repo.json` names javascript in `language` and `summary`.
- A new package still needs an ADR.
