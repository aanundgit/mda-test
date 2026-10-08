# mda-test

Application repo for trying the tool in the sibling folder `mda-copilot`. The Azure DevOps tools stay in that folder. This folder holds the code a story changes.

The stack is static web pages: HTML and CSS, with no build step and no packages. It is recorded in `.mda/repo.json` and `docs/adr/0001-stack-web-frontend.md`.

- `index.html`: the page
- `style.css`: the layout, with a rule for a narrow window
- `tests/`: tests that read the page with the Python `html.parser` module

```bash
python3 -m unittest discover -s tests
```

Open `index.html` in a browser to see the page. A story is written on a branch named `story/<id>-<slug>`.
