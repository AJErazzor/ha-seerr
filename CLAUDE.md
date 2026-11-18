# Working on Seerr Requests

Notes for anyone (person or AI) changing this integration's code.

## Tests

```bash
python -m pytest -q
NODE_PATH=<node_modules with jsdom> node tests/card.test.mjs
```

Setup is described at the top of `requirements_test.txt`. GitHub runs both on every push and pull request.

## Releases

A merge into `main` publishes a HACS release when a commit in it has a message starting with `major:`,
`minor:` or `patch:`, once the tests pass. The release workflow reads commit messages, not the pull request
title, so put the prefix on the commit message (for a squash merge, the commit title) as well as the PR title.
Anything else releases nothing.

The workflow writes the new version into `manifest.json` and the card's `CARD_VERSION`, tags `vX.Y.Z` and
publishes the GitHub Release. Don't bump those by hand.
