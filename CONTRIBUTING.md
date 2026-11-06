# Contributing

Thanks for wanting to make this better. Issues and pull requests are welcome at
https://github.com/vivekbhange-hub/learn-anything-skill.

## Good first contributions

- A skill instruction that led Claude to do the wrong thing: open an issue with what
  you asked, what happened, and what should have happened.
- Better cards, quiz or tutoring rules backed by learning research (link the source).
- Import formats for `anki_export.py` (for example a CSV from another app).
- Fixes for Windows / macOS / Linux differences in the helper scripts.

## Ground rules

- **Helper scripts:** Python 3.9+, standard library only, no network calls, and
  deterministic output (dates come from `--today`, never only from the clock).
  Every script has `--help` and tests in `tests/test_<script>.py`.
- **Skills:** each `skills/learn-*/SKILL.md` keeps the frontmatter `name` equal to
  the folder name, a description with real trigger phrases, numbered steps, and a
  "What NOT to do" section. Keep file formats (`syllabus.md` headings,
  `quiz-log.jsonl`, `mistakes.md`, `cards.md`, `deck.json`) compatible, because the
  skills read each other's files. If you change a format, update every skill that
  reads it and the tests.
- **Agents:** `agents/*.md` use least-privilege tools. Review-only agents do not get
  Write or Edit.
- **Tone:** plain English, no hype, no emoji.

## Running the tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```

All tests must pass on Windows and Linux before a pull request is merged. If you have
Claude Code installed, `claude plugin validate .` checks the plugin manifests too.

## Pull requests

1. Fork, create a branch, make the change with tests.
2. Add a line under an `Unreleased` heading in `CHANGELOG.md`.
3. Describe what changed and why, and how you tried it in Claude Code.

## Conduct

Be kind and assume good faith. This project follows the spirit of the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
