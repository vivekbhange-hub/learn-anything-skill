---
name: learn-quiz
description: >-
  Writes and grades quizzes for a learn/<topic>/ course: multiple choice with
  plausible distractors, short answer, and explain-it-back questions. Grades each
  answer with specific feedback, appends results to quiz-log.jsonl and every miss to
  mistakes.md so later sessions can target them. Use when the user says "quiz me",
  "test me on M3", "give me a practice test", "check if I really get this",
  "mixed quiz on everything so far", "grade my answers", or "exam practice".
argument-hint: "[module ids or 'mixed'] [number of questions]"
---

# learn-quiz

Testing is not only measurement; recalling an answer strengthens the memory more
than rereading. This skill writes quizzes that make the learner retrieve and apply,
grades them honestly, and keeps a record. Misses become the raw material for the
tutor, the flashcards and the progress report.

For a long quiz or one the learner wants graded strictly, delegate writing and
grading to the **quiz-master** agent with the module text and learner level; present
its output here. For short quizzes, do it inline.

## Inputs

- `learn/<slug>/syllabus.md` (objectives are what you test), `learner.md` (level),
  `lessons/m<n>-*.md` if they exist (test what was taught, in its terms).
- Scope from the argument: one module (`M3`), several (`M1 M2`), or `mixed` (all
  modules with lessons). Default: the most recent lesson's module, 6 questions.
- `mistakes.md`: open mistakes in scope get re-tested with a *new* question on the
  same idea, never the identical question.

## Steps

1. **Plan the quiz.** 5-10 questions. Cover every objective in scope at least once.
   Mix of types (rough guide for 6 questions): 3 multiple choice, 2 short answer,
   1 explain-it-back. For `mixed`, interleave modules instead of grouping them:
   switching between problem types is harder and teaches the learner to pick the
   right method, not just execute the last one they saw.

2. **Write each question.**
   - **Multiple choice:** 4 options, one correct. Each distractor must come from a
     real misconception or a likely slip (off-by-one, confusing two related terms,
     the answer to a different question). No "all of the above", no joke options, no
     option that is obviously longer or more hedged than the rest. Shuffle the
     correct letter across questions.
   - **Short answer:** one specific thing to produce: a value, a line of code, a term,
     a prediction. State the format expected.
   - **Explain-it-back:** "Explain <idea> to a colleague who knows <prerequisite> but
     not this, in 3-5 sentences." Grade against 2-4 key points you write down before
     the learner answers.
   Tag each with its module and objective. Write the answer key before showing
   anything, so grading is not bent by the learner's answer.

3. **Save** `learn/<slug>/quizzes/<YYYY-MM-DD>-<scope>.md` with questions only at the
   top and the answer key under a `## Answer key` heading at the bottom.

4. **Deliver.** Show all questions in one message, numbered, without answers. Ask the
   learner to answer all of them in one reply ("1. B  2. ...") and to write "skip"
   rather than guess blindly. Ask them to rate confidence (sure / unsure) per answer
   if they are willing; confident errors are the most valuable to fix.

5. **Grade.** For each question: `correct`, `partial` (short answer or explain-it-back
   with some key points), or `wrong`. Score 1, 0.5 or 0. Feedback per question in
   1-3 sentences:
   - correct: confirm the reason, not just the letter.
   - partial: name the missing key point.
   - wrong: name the misconception the chosen distractor represents, then the
     correct answer with the reason. For explain-it-back, quote the part that is off.
   Accept answers that are correct but phrased differently; grade meaning, not words.
   If the learner's answer reveals the question was ambiguous, give credit and say so.

6. **Log.** Append one JSON line per question to `learn/<slug>/quiz-log.jsonl`:
   ```json
   {"date": "2026-11-07", "module": "M3", "objective": "Write a decorator that preserves metadata", "type": "mcq", "score": 0.5, "correct": false, "confident": true}
   ```
   `type` is `mcq`, `short`, `explain`, or `retrieval`. Append, never rewrite old
   lines. Then append each partial or wrong answer to `learn/<slug>/mistakes.md`:
   ```markdown
   - [ ] 2026-11-07 · M3 · mcq · Thought @wraps copies the return value. Fix: it copies __name__, __doc__ and other metadata from the wrapped function.
   ```
   Create the file with a `# Mistakes` heading if missing. When a previously logged
   mistake is now answered correctly, change its `[ ]` to `[x]`.

7. **Report and hand off.** Show the score (e.g. 4.5 / 6), the objectives that need
   work, and one next step:
   - score under 70% -> **learn-tutor** on the weakest objective
   - misses that are facts or definitions -> **learn-flashcards** for those
   - all good -> next module with **learn-lesson**, or **learn-progress** for the overview

## What NOT to do

- Do not test trivia the lesson never covered, or wording rather than understanding.
- Do not reveal answers before the learner submits.
- Do not round partials up to be kind, or mark a right answer wrong because it does not
  match your phrasing.
- Do not delete or rewrite lines in quiz-log.jsonl; progress depends on the history.
- Do not quiz a module that has no lesson and no source material unless the learner
  asks for a pre-test, and then log nothing to mistakes.md.
