# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-07

### Added
- Skills: `learn-syllabus`, `learn-lesson`, `learn-quiz`, `learn-flashcards`,
  `learn-review`, `learn-repo`, `learn-tutor`, `learn-progress`.
- Agents: `socratic-tutor`, `quiz-master`, `explainer`.
- `anki_export.py`: cards.md / JSON to Anki TSV (basic and cloze), deduplication,
  atomicity checks, stable card ids, JSON export for the reviewer.
- `srs.py`: SM-2 spaced repetition over a JSON deck with `add`, `due`, `show`,
  `grade` and `stats`, deterministic via `--today`.
- `progress.py`: per-module mastered / shaky / in progress / not started report from
  the quiz log, deck, mistakes and lessons.
- Unit tests for every helper script and a repository structure test.
