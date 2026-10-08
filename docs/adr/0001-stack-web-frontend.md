# 0001. Stack for web-frontend work

Date: 2026-10-08

Status: Accepted. The signed-in person confirmed build_setup for story 1423.

## Decision

This repo is a web-frontend project. Static web pages: HTML and CSS. No build step and no packages.

| | |
|---|---|
| Language | html, css |
| Framework | none |
| Runtime | static-hosting |
| Test | `python3 -m unittest discover -s tests` |
| Build | none |
| Template | none |

## Layout

- index.html: the page
- style.css: the layout, with a rule for a narrow window
- tests/: tests that read the page with the Python html.parser module

## Consequences

- Every story in this repo follows `.mda/repo.json`. The build agent reads it before it writes code.
- A new package needs an ADR.
- The agent never deploys. The company pipeline builds, scans, and deploys.
- Changing the stack needs a new ADR and an edit to `.mda/repo.json`.
