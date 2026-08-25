# alphaloop

alphaloop is being rebuilt from scratch.

The previous implementation has been removed from the working tree as part of a
product redesign. This repository is intentionally an empty skeleton while the
greenfield rewrite is designed; new code will land here from scratch.

The old code is not gone — git history is fully intact. Anything from the
previous implementation can be recovered from the commit before the wipe:

```bash
git log --oneline            # find the commit before the greenfield wipe
git show <commit>:<path>     # read a single old file
git checkout <commit> -- .   # restore the old tree locally
```

## What is here

- `README.md` — this file
- [`docs/requirements/product-positioning.md`](./docs/requirements/product-positioning.md) — the product positioning for alphaloop
- [`docs/requirements/product-design-v0_0_1.md`](./docs/requirements/product-design-v0_0_1.md) — the v0.0.1 product design (features, IA, flows)
- `LICENSE` — MIT
- `.gitignore` — minimal Python/generic ignores

## License

MIT. See [`LICENSE`](./LICENSE).
