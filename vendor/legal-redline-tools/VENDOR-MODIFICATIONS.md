# Vendored modifications

This directory is derived from `legal-redline-tools` tag `v0.2.0`, upstream
commit `eef61a0cb6afe2867fde70335c179d4a6ad298c8`.

The upstream MIT `LICENSE` is retained unchanged. A direct comparison with the
tag found:

- unchanged upstream files: `LICENSE`, `examples/sample-redlines.json`,
  `legal_redline/__init__.py`, `legal_redline/diff.py`,
  `legal_redline/memo.py`, and `legal_redline/scan.py`;
- modified files: `CHANGELOG.md`, `README.md`, `pyproject.toml`, and
  `legal_redline/apply.py`, `cli.py`, `compare.py`, `markdown.py`, `remap.py`,
  `render.py`, and `summary.py`;
- locally added files: the `tests/` tree; and
- omitted upstream repository-support files: `.gitignore` and `skill.md`.

The local changes improve tracked-change placement and validation, document
rendering behavior, command-line handling, normalization, summaries,
documentation, packaging, and regression coverage. In particular, applying a
new redline now refuses source packages that already contain revision/comment
markup, stages multi-format outputs, and refuses existing, duplicate,
source-colliding, or symlinked output targets. They remain distributed
under the upstream MIT terms. This inventory records technical provenance; it
does not determine copyright ownership of AI-assisted changes.
