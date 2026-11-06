---
name: learn-lesson
description: >-
  Teaches one module of a learn/<topic>/ course as an active lesson: a hook,
  a short explanation, a fully worked example, a faded example the learner finishes
  themselves, then three retrieval questions. Depth follows the learner's diagnosed
  level. Saves the lesson to learn/<topic>/lessons/. Use when the user says "teach me
  M2", "next lesson", "start module 1", "explain closures properly", "continue the
  course", "let's do today's lesson", or "I'm ready for the next part".
argument-hint: "[module id, e.g. M2]"
---

# learn-lesson

Teaches one module the way learning research says works: explanation is short, the
learner studies a complete worked example, then does a partially worked one where
the final steps are removed (fading), then pulls the ideas back out of memory with
retrieval questions. Reading a good explanation feels like learning; producing the
answer is what actually builds it. This skill makes sure the learner produces.

## Inputs

- `learn/<slug>/syllabus.md` and `learn/<slug>/learner.md` (from learn-syllabus).
  If there are several course folders under `learn/`, ask which one. If none exists,
  offer to run **learn-syllabus** first, or teach a one-off lesson without saving.
- Module id from the argument. With no argument, pick the first module with no file
  in `lessons/` whose prerequisites all have lessons.
- `learn/<slug>/tours/NN-*.md` for a codebase course built by **learn-repo**: the
  tour is the source for that module, and its stops are where examples come from.
- `learn/<slug>/mistakes.md` if present: open mistakes in this module's prerequisites
  are worth one sentence of repair in the hook.

## Steps

1. **Read the module** in syllabus.md: objectives, prerequisites, time. Read
   learner.md for level and preferences. If a prerequisite module has never been
   taught, say so and offer to do it first; continue only if the learner insists.

2. **Set depth by level.**
   - `new`/`beginner`: concrete before abstract, one idea per step, everyday analogy,
     define every term on first use, small numbers and short code.
   - `intermediate`: lead with the mental model, contrast with what they already know,
     include one common misconception.
   - `advanced`: skip basics, go to mechanism, trade-offs, edge cases, and where the
     simple model breaks.

3. **Teach in this order, pausing where marked.** Keep each part tight.

   **a. Hook (2-4 sentences).** A question or puzzle the module will let them answer,
   ideally one they get wrong right now. Ask them to guess before reading on. Wait.

   **b. Explanation.** Cover each objective in plain language, at most ~250 words per
   objective. One diagram in a code block if structure matters. End with a one-line
   summary per objective.

   **c. Worked example.** A complete problem solved step by step, each step labeled
   with *why* it is taken, not only what. Choose a problem that exercises the
   objectives together.

   **d. Faded example.** A parallel problem (same structure, new surface) where the
   first steps are shown and the last 1-3 steps are blank (`Step 3: ____`). For
   `advanced` learners fade everything after step 1. Ask the learner to fill the
   blanks. **Wait for their answer.** Then give feedback: what is right, the exact
   point where it goes wrong if it does, and one hint to fix it before showing the
   correct step. If they are stuck after one hint, hand off to the same hint ladder
   **learn-tutor** uses (nudge, strategy, partial step), then reveal.

   **e. Retrieval questions (exactly 3).** Without the explanation in view:
   1. recall: state or define a key idea in their own words,
   2. apply: use it on a fresh small case,
   3. connect: relate it to a prerequisite or predict what happens if something changes.
   Ask all three, wait, then grade each: correct / partly / not yet, with one line of
   feedback. Log each to `quiz-log.jsonl` and misses to `mistakes.md` using the
   formats in **learn-quiz** (type `retrieval`).

4. **Write `learn/<slug>/lessons/m<n>-<module-slug>.md`** containing the hook, the
   explanation, both examples with the correct faded steps, the three retrieval
   questions with model answers, and a "Your answers" section summarizing how the
   learner did. This is their notes; keep it clean and re-readable.

5. **Close.** In 3 lines: what they can now do (objectives as verbs), one thing to
   watch out for, and the next step:
   - any retrieval miss -> "Want to work on <miss> with the tutor?" (**learn-tutor**)
   - all correct -> "Make flashcards for this module?" (**learn-flashcards**), then
     "Quiz on M<n> tomorrow" (**learn-quiz**) because a delay makes retrieval stronger.

## Decision rules

- If the learner answers the hook correctly with a good reason, shorten the
  explanation and spend the time on the faded example and a harder variant.
- If two of three retrieval questions are missed, do not move to the next module.
  Re-teach the missed objective with a different example, then ask one new question.
- Prefer examples from the learner's own domain (learner.md preferences, the
  source document, or their project) over textbook ones.
- If the learner says the explanation is over their head or too basic, ask the
  **explainer** agent for the same idea at five levels, let them pick one, and
  continue the lesson at that depth (and note the preference in learner.md).
- Use the syllabus source document as the authority when there is one; quote its
  section names so they can go back to it.

## What NOT to do

- Do not dump the whole lesson in one message. The pauses at the hook, the faded
  example and the retrieval questions are the point.
- Do not answer the faded example or retrieval questions for the learner before they
  try. "I don't know" is a valid try; respond with a hint, not the answer.
- Do not praise vaguely ("Great job!"). Say what exactly was right.
- Do not cover objectives that belong to later modules; note them as "coming in M<n>".
- Do not exceed the module's time estimate by more than half; split into two sessions
  instead and say where you stopped.
