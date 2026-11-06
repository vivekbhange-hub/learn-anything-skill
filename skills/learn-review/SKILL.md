---
name: learn-review
description: >-
  Runs a spaced-repetition review session from learn/<topic>/deck.json: shows each
  due card's question, waits for the learner's answer, compares it with the back,
  agrees a 0-5 grade and reschedules the card with the SM-2 algorithm through a
  deterministic helper script. Reports what is due next. Use when the user says
  "review my cards", "what's due today", "daily review", "spaced repetition",
  "run my flashcards", "how many cards are due", or "deck stats".
argument-hint: "[topic slug] [max cards]"
---

# learn-review

Spacing beats cramming: a fact reviewed just before it would be forgotten lasts much
longer than one reviewed five times in an evening. This skill runs the daily review,
keeps the learner honest about whether they really recalled the answer, and lets the
helper script do the scheduling arithmetic so intervals are exact and reproducible.

The scheduler is `srs.py` (SM-2: ease factor, interval, repetition count, due date).
Always pass `--today YYYY-MM-DD` with today's date so every run is reproducible.

```bash
SRS="${CLAUDE_SKILL_DIR}/srs.py"
python3 "$SRS" learn/<slug>/deck.json due --today 2026-11-07 --limit 20
python3 "$SRS" learn/<slug>/deck.json show <id>
python3 "$SRS" learn/<slug>/deck.json grade <id> <0-5> --today 2026-11-07
python3 "$SRS" learn/<slug>/deck.json stats --today 2026-11-07
```

Card ids can be shortened to any unique prefix (`grade c3f1 4`).

## Steps

1. **Find the deck.** `learn/<slug>/deck.json`. If there are several course folders,
   ask which, or offer to review each in turn. No deck: offer **learn-flashcards**.

2. **List due cards** with `due --json --limit <n>` (default 20; new cards count).
   If nothing is due, show `stats` and the next due date, and stop. Do not review
   cards early just to have something to do; early reviews add little.

3. **Run the session, one card at a time.**
   a. Show only the question (the `front` from `due --json`, already masked for
      cloze cards). Ask the learner to answer before revealing anything.
   b. After they answer, run `show <id>` to get the back and compare meaning, not
      wording.
   c. Propose a grade and the reason, and let the learner change it:
      - 5: correct, instant
      - 4: correct after a moment's thought
      - 3: correct but with real effort, or a small slip
      - 2: wrong, but the answer felt familiar on seeing it
      - 1: wrong, the answer barely rang a bell
      - 0: no idea
      Learners overrate themselves when grading alone; if the answer was partially
      wrong, the grade is 2 at most.
   d. Run `grade <id> <grade>` and mention the next interval in a few words
      ("see you in 6 days").
   e. On a grade below 3, give a one-line explanation or memory hook, and put the
      card in a "retry" list.

4. **Retry pass.** After the due list, ask each retry card once more. Do not grade
   them again (SM-2 records one grade per card per day); this pass is only so the
   session ends on a correct recall.

5. **Wrap up.** Run `stats` and report in 3-4 lines: cards reviewed, how many
   recalled (grade >= 3), retention over the last 30 days, cards due tomorrow, and any
   leeches (cards lapsed 4+ times).

6. **Deal with leeches.** A leech is usually a bad card, not a bad learner. Look at
   the card: too big, ambiguous, or confusing two similar ideas? Offer to rewrite it
   in `cards.md` via **learn-flashcards** (split it, add context, or add a contrast
   card), or to work the idea through with **learn-tutor**.

7. **Hand off.** If 3+ cards from the same module failed, suggest **learn-quiz** or
   **learn-tutor** on that module. Otherwise suggest the next lesson or
   **learn-progress** for the big picture.

## SM-2 in one paragraph (for explaining to the learner)

Each card has an ease factor (starts at 2.5). A pass (grade 3+) moves the card from
1 day to 6 days, then multiplies the interval by the ease each time. A fail resets the
card to 1 day. Every grade nudges the ease: 5 raises it by 0.1, 4 leaves it, 3 lowers
it by 0.14, a 0 lowers it by 0.8; it never drops below 1.3. Hard cards come back
often, easy cards drift out to months.

## What NOT to do

- Do not show the answer before the learner has tried.
- Do not grade a card twice on the same day, and do not hand-edit deck.json.
- Do not inflate grades to make the stats look good; a lie in the grade schedules
  the card too late and the learner forgets it.
- Do not run reviews without `--today`; the date makes results reproducible and
  testable.
- Do not let a session run past ~20 minutes or ~50 cards; stop and say how many
  remain. Short daily sessions beat long weekly ones.
