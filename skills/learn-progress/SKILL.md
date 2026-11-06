---
name: learn-progress
description: >-
  Writes a progress report for a learn/<topic>/ course: classifies every syllabus
  module as mastered, shaky, in progress or not started from the quiz log, card
  reviews and open mistakes, with a deterministic helper script, then says exactly
  what to do next. Use when the user says "how am I doing", "show my progress",
  "what should I study next", "am I ready for the exam", "what am I weak at",
  "progress report", or "where did I leave off".
argument-hint: "[topic slug]"
---

# learn-progress

Learners are poor judges of their own knowledge: material that feels familiar after
rereading often cannot be recalled a week later. This skill replaces the feeling
with evidence. It reads what the other learn-* skills recorded, applies fixed rules,
and turns the result into a short list of next actions, ordered so that repair and
review come before new material.

The classification is done by `progress.py`, so the same files always give the same
report:

```bash
python3 "${CLAUDE_SKILL_DIR}/progress.py" learn/<slug> --today 2026-11-07 --out learn/<slug>/progress.md
```

Add `--json` for machine-readable output.

## What it reads

| File | Written by | Used for |
|---|---|---|
| `syllabus.md` (`## M1. Title` headings) | learn-syllabus, learn-repo | module list (required) |
| `lessons/m<n>-*.md` | learn-lesson | lesson taught |
| `quiz-log.jsonl` | learn-quiz, learn-lesson, learn-tutor | quiz accuracy (last 10 per module) |
| `deck.json` | learn-review (srs.py) | card retention, cards due (via `m<n>` tags) |
| `mistakes.md` | learn-quiz, learn-tutor | open mistakes per module |

## Status rules

- **not started**: no lesson, no quiz attempts, no reviewed cards.
- **mastered**: 5+ quiz attempts, 85%+ accuracy over the last 10, card retention
  85%+ (or no reviewed cards yet), and no open mistakes.
- **shaky**: under 70% accuracy over 3+ attempts, or under 80% retention over 5+
  card reviews, or 3+ open mistakes.
- **in progress**: started, but not enough evidence for either (the honest answer
  when there have been only a couple of attempts).

## Steps

1. **Find the course.** `learn/<slug>/`; if there are several, report on the one
   used most recently (newest file) and list the others in one line. No syllabus:
   offer **learn-syllabus**.

2. **Run progress.py** with today's date and `--out learn/<slug>/progress.md`. If
   it reports skipped unreadable lines in quiz-log.jsonl, look at them and fix the
   format (do not delete history).

3. **Optionally add deck health** with
   `python3 "${CLAUDE_SKILL_DIR}/../learn-review/srs.py" learn/<slug>/deck.json stats --today <date>`
   when a deck exists: overall retention and leeches belong in the summary.

4. **Read the evidence behind shaky modules.** For each shaky module, read its open
   lines in mistakes.md and its last few quiz-log entries, and name the pattern in one
   sentence ("Misses are all about when the closure captures the variable, not about
   syntax."). That sentence is the most useful line in the report.

5. **Present the report** in chat, short:
   - one line: counts per status and cards due;
   - the module table from progress.md (it is already written to the file);
   - the pattern sentence for each shaky module;
   - "Next" as at most 3 numbered actions, each naming the skill to run. Use the
     script's order: due reviews, then repairing shaky modules, then gathering
     evidence for in-progress modules, then the next new module, then the capstone.

6. **Answer readiness questions honestly.** For "am I ready for the exam / the
   capstone?": ready only if every module the goal depends on is mastered. Otherwise
   say which modules stand in the way and roughly how many sessions each needs
   (one session per shaky module, two if it has 5+ open mistakes).

7. **Hand off** by offering to start action 1 right away.

## What NOT to do

- Do not mark anything mastered by impression, or because a lesson was finished. The
  rules are the rules; if the learner disagrees, the fix is a quiz, not an override.
- Do not edit quiz-log.jsonl, deck.json or mistakes.md here; this skill only reads
  and writes progress.md.
- Do not pad the report with encouragement. One honest sentence about what went well
  is enough.
- Do not recommend more than three next actions at once.
