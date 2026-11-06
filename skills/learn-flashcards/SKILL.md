---
name: learn-flashcards
description: >-
  Writes atomic flashcards (one fact per card, cloze deletions where context helps)
  for a module, a document or past quiz mistakes, saves them to learn/<topic>/cards.md,
  then runs a helper that deduplicates, checks card length and exports Anki-importable
  TSV files plus a JSON deck for spaced review. Use when the user says "make flashcards",
  "turn this into Anki cards", "cards for M2", "export to Anki", "flashcards from my
  mistakes", "cloze cards from this paragraph", or "add these to my deck".
argument-hint: "[module id, file, or 'mistakes']"
---

# learn-flashcards

Good cards are small. A card that asks for five things gets half-remembered and
graded as a pass, and the other half quietly decays. This skill writes cards that
each test one retrievable fact, phrased so the question cannot be answered by
pattern-matching the wording, then exports them for Anki and for this pack's own
spaced-repetition reviewer (**learn-review**).

## Inputs

- Scope: a module id (`M2`, read its lesson in `learn/<slug>/lessons/`), a file or
  pasted text, or `mistakes` (open lines in `learn/<slug>/mistakes.md`).
- Existing `learn/<slug>/cards.md`: append to it; never rewrite cards that are there.

## Steps

1. **Pick what deserves a card.** Facts, definitions, distinctions, small procedures,
   "what happens when", and every open mistake. Skip what the learner can easily
   derive, and skip whole explanations (those belong in lessons, not cards).
   Aim for 5-15 cards per module.

2. **Write atomic cards.** Rules:
   - One fact per card. If the answer has "and", consider two cards.
   - The question must be answerable without seeing other cards; include context
     ("In Python, ..." / "In SM-2, ...").
   - Answer short: a word, a number, a phrase, one line of code, one sentence.
   - Prefer "why" and "what happens if" cards over pure term-definition pairs; aim
     for at least a third of cards that way.
   - Lists: do not ask "name the 5 X". Use one cloze card per item in a sentence that
     gives a reason, or ask about the item that is most often forgotten.
   - Use cloze (`{{c1::...}}`) when the surrounding sentence is the context that makes
     the fact meaningful. One or two deletions per card at most. A hint after `::` is
     allowed: `{{c1::ease factor::SM-2 term}}`.
   - For mistake cards, aim the question at the exact confusion logged, and put the
     correct idea in the answer.
   - Tag every card with its module id in lowercase (`m2`) plus one or two topic tags.
     The module tag is what learn-progress uses to attribute card reviews.

3. **Append to `learn/<slug>/cards.md`** in this block format (blank line between
   cards; keys are `Q:`/`A:` for basic cards, `C:`/`Extra:` for cloze, `Tags:`):

   ```markdown
   Q: In SM-2, what happens to a card's repetition count after a grade below 3?
   A: It resets to 0, so the interval restarts at 1 day.
   Tags: m2 srs

   C: An ease factor never drops below {{c1::1.3}} in SM-2.
   Extra: Without a floor, hard cards would be shown every day forever.
   Tags: m2 srs
   ```

   Code can go in fenced blocks inside a field. No prose between cards; a heading per
   module is fine.

4. **Validate and export.** Run:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/anki_export.py" learn/<slug>/cards.md \
     --json-out learn/<slug>/cards.json --tag <slug>
   ```

   It writes `learn/<slug>/anki-basic.tsv` (and `anki-cloze.tsv` if there are cloze
   cards), merges duplicates (same question ignoring case and punctuation; tags are
   unioned), and prints warnings to stderr. Exit code 1 means some cards were dropped
   (empty answer, cloze with no deletion, identical front and back).
   Fix every error and every warning about length, list-like answers, or an answer
   that appears in the question by editing cards.md, then run it again. Use `--check`
   to validate without writing.

5. **Feed the reviewer.** Add the cards to the spaced-repetition deck (new cards are
   due today; existing cards keep their schedule, their text is refreshed):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/../learn-review/srs.py" learn/<slug>/deck.json add learn/<slug>/cards.json
   ```

6. **Tell the learner how to import into Anki** (only if they use Anki):
   File > Import > choose `anki-basic.tsv`. Anki 2.1.55+ reads the header lines and
   picks the note type and tag column itself. For cloze, import `anki-cloze.tsv`
   separately. On older Anki, rerun with `--no-headers` and pick "Basic" or "Cloze",
   field separator Tab, "Allow HTML", and map column 3 to Tags.

7. **Hand off.** Report "<n> cards added (<k> cloze), <d> duplicates merged" and
   offer a first review now with **learn-review** (new cards are due today).

## What NOT to do

- Do not make cards whose answer is a paragraph, a list of more than three items, or
  "it depends".
- Do not copy sentences from the source and blank out a random word; blank out the
  word that carries the idea.
- Do not edit `deck.json` by hand; always go through srs.py so schedules stay valid.
- Do not remove a card from cards.md because the learner got it wrong; wrong cards
  are the useful ones. Rewrite it only if it was badly phrased.
- Do not import into Anki or touch the learner's Anki profile; give them the file.
