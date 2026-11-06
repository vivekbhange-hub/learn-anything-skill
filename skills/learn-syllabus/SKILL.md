---
name: learn-syllabus
description: >-
  Starts a personal course on any topic, document or skill. Asks 3-5 diagnostic
  questions to find the learner's real level, then writes learn/<topic>/syllabus.md
  with modules, verb-based learning objectives, prerequisites, time estimates and a
  capstone project, plus learner.md with the diagnosis. Use when the user says
  "I want to learn X", "teach me Y from scratch", "make me a course on Z",
  "build a study plan for this doc", "where do I start with Rust",
  "turn this PDF into a syllabus", or "I have two weeks to learn SQL".
argument-hint: "[topic, file path, or URL]"
---

# learn-syllabus

Builds the map before the journey. A syllabus written for "a beginner" in general
wastes the time of someone who already knows half of it, and loses someone who is
missing a prerequisite. So this skill measures first, with a few targeted diagnostic
questions, and only then writes a course sized to what this learner knows, how much
time they have, and what they want to be able to do at the end.

Everything is written to `learn/<topic-slug>/` in the current project. Other learn-*
skills read these files, so keep the formats below exactly.

## Steps

1. **Pin down the topic and the goal.** From the argument or conversation, get:
   - the topic (or source: a file path, a folder, pasted text). If the source is a
     codebase, stop and use **learn-repo** instead.
   - the goal: what the learner wants to *do* afterwards ("pass the AWS SAA exam",
     "read research papers on transformers", "ship a CLI in Go"). Ask once if missing.
   - time budget: hours per week and a deadline, if any. Default to 3 h/week.
   Make the slug: lowercase ASCII, words joined by `-`, at most 40 chars
   (`python-decorators`, `aws-saa-exam`). If `learn/<slug>/syllabus.md` already
   exists, read it and ask whether to revise or start a new course; never overwrite
   silently.

2. **If the source is a document**, read it fully first (Read for files; for long
   files read in parts). Note its section structure and the terms it assumes. The
   syllabus must follow what the document actually covers; mark anything you add
   from general knowledge as `(beyond the source)`.

3. **Run the diagnostic: 3-5 questions, one at a time.** Design them as a ladder:
   - Q1 checks a prerequisite ("What does a function return if it has no `return`?").
   - Q2-Q3 check the core idea at the level of using it.
   - Q4-Q5 check transfer: apply it to a new case, or spot the bug.
   Ask open questions, not multiple choice, so guessing does not inflate the level.
   Add "Say 'skip' if you have no idea; that is useful information." After each
   answer, do not teach or correct at length; note it and move on. If the first two
   answers are both blank or wrong, stop the ladder early: the learner is a beginner.

4. **Place the learner** on one of four levels and write the evidence:
   - `new`: missed the prerequisite question.
   - `beginner`: has prerequisites, cannot yet use the core idea.
   - `intermediate`: uses the core idea, fails transfer questions.
   - `advanced`: answers transfer questions; wants depth, edge cases, internals.
   Tell the learner the placement in one sentence with the reason, and let them
   override it.

5. **Design the modules.** 4-8 modules for most topics; each sized at 30-120 minutes
   of study. Order by dependency, not by the source's table of contents. Skip modules
   the diagnostic shows are already known, but list them under "Already solid" so
   the learner can see why. Every module gets:
   - 2-4 learning objectives that start with an observable verb (explain, compare,
     predict, write, debug, choose, derive, trace). Never "understand" or "know".
   - prerequisites as module ids (`M1, M3`) or `none`.
   - a time estimate in minutes.
   - one line on how mastery will be checked (what the quiz will ask them to do).

6. **Design the capstone.** One project that needs most modules, produces something
   the learner can show or use, and fits in 2-6 hours. Give it acceptance criteria
   (3-5 checkable bullets) and list the modules it draws on.

7. **Write `learn/<slug>/syllabus.md`** in exactly this shape (progress.py parses the
   `## M<n>.` headings):

   ```markdown
   # Syllabus: <Topic>

   Goal: <what the learner will be able to do>
   Level: <new|beginner|intermediate|advanced> (diagnosed <YYYY-MM-DD>)
   Time: <total hours> over <weeks> weeks at <h>/week
   Source: <file/URL or "general knowledge">

   ## M1. <Module title>
   - Objectives:
     - <Verb> <specific thing>
     - <Verb> <specific thing>
   - Prerequisites: none
   - Time: 45 min
   - Mastery check: <what they must do>

   ## M2. ...

   ## Capstone: <project name>
   <2-3 sentences>
   - Uses: M1, M3, M4
   - Done when:
     - [ ] <checkable criterion>

   ## Already solid
   - <topic> (diagnostic Q2 answered correctly)
   ```

8. **Write `learn/<slug>/learner.md`**: the goal, time budget, level, each diagnostic
   question with the learner's answer and your one-line verdict, and any preferences
   they mentioned (examples in Python, likes analogies, prefers short sessions).
   Other skills read this to set depth.

9. **Close the loop.** Show the module list as a short table (id, title, time), then
   offer the next step: "Start M1 now?" which runs **learn-lesson** on M1.

## Decision rules

- Fewer modules beat more. If two modules share all objectives, merge them.
- A module with no prerequisites should come early; a module needed by the capstone
  must not be optional.
- Deadline too short for the material: say so plainly, then cut scope to the goal
  (drop nice-to-have modules into an "Later" list) rather than squeezing times.
- Time estimates include practice, not just reading: roughly 1/3 explanation, 2/3
  retrieval and exercises.

## What NOT to do

- Do not skip the diagnostic because the learner said "I'm a beginner". Self-reports
  are often wrong in both directions. Two quick questions still beat zero.
- Do not ask all diagnostic questions in one message; one at a time, so each answer
  can shape the next.
- Do not write objectives with "understand", "learn about", "be familiar with".
- Do not invent facts about a provided document; cite its sections instead.
- Do not start teaching inside this skill. Diagnosis and planning only; teaching is
  learn-lesson's job.
