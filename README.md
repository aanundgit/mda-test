# mda-test

Application repo for trying the tool in the sibling folder `mda-copilot`. The Azure DevOps tools stay in that folder. This folder holds the code a story changes.

The stack is the approved library: a Python package and unittest, standard library only.

```bash
python3 -m unittest discover -s tests
```

The tool writes a story on a branch named `story/<id>-<slug>` in the repo its map selects. Dispatch still goes to `mda-copilot-pilot`. Digital still goes to `mda-copilot-pilot/web`. A department that is not in `context/repos.json` uses `MDA_APP_DIR` from the tool's `.env`. Point that setting at this folder to try a story here.
