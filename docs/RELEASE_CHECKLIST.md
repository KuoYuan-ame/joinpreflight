# JoinPreflight release checklist

## Before migrating
- [ ] Save a Git commit or copy of the current working project.
- [ ] Do not rename `.venv` or modify Olist source CSV files.
- [ ] Confirm the PyPI name at https://pypi.org/project/joinpreflight/ and check availability at release time.
- [ ] Choose a GitHub account/repository name and replace `YOUR_GITHUB_USERNAME` in `README.md` and `pyproject.toml`.

## Migrate
- [ ] Rename `src/granguard/` to `src/joinpreflight/` and update references in `src/`, `tests/`, and `examples/` (or run the included PowerShell script).
- [ ] Replace the root `pyproject.toml`; copy `README.md`, `.gitignore`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, and `.github/workflows/` into the project root.
- [ ] Uninstall the old package `granguard`; install `joinpreflight` using `python -m pip install -e ".[dev]"`.
- [ ] Verify `python -c "import joinpreflight; print(joinpreflight.__file__)"` and `joinpreflight --help`.
- [ ] Run `python -m pytest -v` and an end-to-end Olist CLI check.
- [ ] Inspect for stale `granguard` references in source/config/documentation.
- [ ] Check build using `python -m build` and `python -m twine check dist/*`.

## Publish on GitHub
- [ ] Create a public repository named `joinpreflight` (without adding auto-generated files if pushing an existing repo).
- [ ] Push `main`, check all CI jobs are green, and verify rendered README.
- [ ] Verify that large CSV datasets and secrets are excluded by `.gitignore`.
- [ ] Tag `v0.1.0` only after tests/CI pass; pushing the tag triggers `.github/workflows/release.yml`.
- [ ] Verify the GitHub Release and attached `.whl` and `.tar.gz` assets.
- [ ] Do not claim availability on PyPI until a separate PyPI release succeeds.

## Future PyPI release
- [ ] Confirm exact normalized distribution name remains available on PyPI.
- [ ] Configure PyPI Trusted Publishing with exact repo owner, repo name, and workflow filename.
- [ ] Consider TestPyPI and verify install from a clean environment before pushing to PyPI.
