---
name: learn-repo
description: >-
  Turns a codebase into a hands-on course: maps its structure, picks a reading order,
  writes guided tours of the key files grounded in real line references, and sets
  exercises such as "trace this request end to end", "predict what this test does",
  and "add a small feature", each with escalating hints. Saves everything under
  learn/<repo-slug>/. Use when the user says "help me learn this codebase",
  "onboard me to this repo", "teach me how this project works", "I just joined,
  where do I start", "make a course out of this repo", or "give me exercises on this code".
argument-hint: "[path to repo, default: current directory]"
---

# learn-repo

Reading a codebase top to bottom is slow and forgettable. People learn a codebase
by following one real path through it, predicting what the code will do, and then
changing something small and seeing it work. This skill builds that path: a reading
order, tours that explain the files that matter, and exercises with hints so the
learner does the thinking. Every claim points at a real file and line.

## Output

```
learn/<repo-slug>/
  syllabus.md          modules = stops on the reading order (same format as learn-syllabus)
  learner.md           goal and level (ask 2-3 questions, see step 2)
  tours/01-<name>.md   one guided tour per module
  exercises.md         exercises with hints and answer keys in collapsed sections
```

Using the syllabus format means **learn-quiz**, **learn-flashcards**,
**learn-tutor** and **learn-progress** work on the repo course unchanged.

## Steps

1. **Survey, read-only.** Use Glob/Grep/Read and `git log --oneline -20` if it is a
   git repo. Find: README and docs, the manifest (package.json, pyproject.toml,
   go.mod, Cargo.toml, pom.xml...), entry points (main, cli, server start, app
   factory, routes), the test layout, config, and the 10-20 files with the most
   inbound references (grep for imports of each module). Skip vendored, generated,
   lock and build output folders. For very large repos, ask which area matters and
   scope to it.

2. **Ask the learner 2-3 questions**, one at a time: what they need to do in this
   codebase (fix bugs, add features in area X, review PRs), how comfortable they are
   with the language and framework, and how much time they have. Write learner.md
   with the answers and a level (new / beginner / intermediate / advanced in this
   stack).

3. **Choose the spine.** Pick one representative flow that touches most layers: an
   HTTP request, a CLI command, a job, a render, a message. Trace it yourself first,
   recording each hop as `path:line function`. This trace is the backbone of the course.

4. **Write syllabus.md** with modules in reading order, usually:
   M1 what it does and how to run it (setup, run, run the tests);
   M2 the map (top-level folders, what lives where, naming conventions);
   M3 the entry point and the spine flow, hop by hop;
   M4-M6 the core domain model, the data layer, the cross-cutting pieces (auth,
   config, errors, logging) as relevant;
   M7 the tests and how changes are verified.
   Objectives are verbs about this code: "trace a request from `routes/orders.py`
   to the database", "explain why `CacheLayer` is invalidated in `save()`".
   Capstone: a small but real change the learner could ship (see step 6).

5. **Write one tour per module** in `tours/NN-<name>.md`:
   - why this part exists, in two sentences;
   - stops: 3-8 files or functions, each with `path:line`, a short excerpt (at most
     ~15 lines, quoted exactly), what to notice, and how it connects to the next stop;
   - "Predict before you read" prompts at 1-2 stops ("What will `parse()` return for
     an empty file? Write your guess, then read lines 40-58.");
   - a closing "You should now be able to" list matching the objectives.
   Verify every path and line number with Read before writing it down.

6. **Write exercises.md**, 6-10 exercises, ordered easy to hard, mixing these kinds:
   - **Trace:** "Trace what happens when <input>. List each function called, in order."
   - **Predict:** "What does this test assert, and why would it fail if line N changed?"
   - **Locate:** "Where is <behavior> decided? Find it without searching for the word X."
   - **Modify:** "Change <small behavior>. Which files must change? Make the test pass."
   - **Extend:** "Add <small feature> following the existing pattern in <file>."
   - **Debug:** describe a realistic bug the learner should be able to find.
   Each exercise has: goal, starting point (`path:line`), a check ("the test X
   passes", "the output shows Y"), then three hints of increasing strength and an
   answer key, each in its own `<details><summary>Hint 1</summary>...</details>`
   block so the learner opens them deliberately.
   Exercises that change code are done on a branch or a scratch copy; say so in the
   exercise, and never commit for the learner.

7. **Hand off.** Show the reading order as a short list and suggest starting with
   M1. The learner can read a tour alone, or study it actively with
   **learn-lesson M1**, which uses the tour as its source and records the lesson in
   `lessons/` (that is what learn-progress counts as taught; writing a tour does not).
   When the learner works an exercise and gets stuck, run **learn-tutor** with the
   exercise as the problem; the hints in exercises.md are its ladder. After each
   module, **learn-quiz** works as usual.

## Decision rules

- Prefer the path the learner will actually work on (from step 2) as the spine.
- If the repo has no tests, the M7 module becomes "how to check a change by hand",
  and one exercise is writing the first test.
- If the setup does not run (missing services, secrets), say so in M1 and design
  exercises that need only reading and the unit tests.
- Mention generated code and magic (decorator registration, dependency injection,
  metaprogramming) explicitly; that is where newcomers get lost.

## What NOT to do

- Do not modify the repo's source files. All output goes under `learn/`.
- Do not invent file paths, function names or line numbers; read before citing.
- Do not tour every file. A tour that covers everything teaches nothing.
- Do not paste large blocks of the code into tours; quote the lines that matter and
  point to the rest.
- Do not run install scripts, migrations or anything that touches external services
  without asking the learner first.
