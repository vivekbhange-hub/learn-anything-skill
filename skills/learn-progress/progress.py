#!/usr/bin/env python3
"""Progress report for one course folder (learn/<topic-slug>/).

Reads what the other learn-* skills write and classifies every syllabus module:

  syllabus.md      module headings like "## M1. Title"         (required)
  lessons/         files named m1-*.md mark a taught lesson
  quiz-log.jsonl   one graded question per line:
                   {"date": "2026-11-07", "module": "M1", "correct": true, "score": 1.0}
  deck.json        srs.py deck; cards tagged m1, m2, ... count toward that module
  mistakes.md      "- [ ] ... M2 ..." open, "- [x] ..." fixed

Status rules (evidence first, never a guess):
  not started  no lesson, no quiz attempts, no reviewed cards
  mastered     >= 5 quiz attempts, accuracy over the last 10 >= 85%,
               card retention >= 85% (or no reviewed cards), 0 open mistakes
  shaky        accuracy < 70% over >= 3 attempts, or retention < 80% over
               >= 5 card reviews, or >= 3 open mistakes
  in progress  anything else (started, not enough evidence yet)

Writes Markdown (default) or JSON. Deterministic with --today.
Standard library only, no network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MODULE_HEADING_RE = re.compile(r"^#{2,3}\s+(?:Module\s+)?M?(\d+)\b\s*[.:)\-–—]*\s*(.*?)\s*$", re.I)
TITLE_RE = re.compile(r"^#\s+(?:Syllabus\s*[:\-–—]\s*)?(.+?)\s*$", re.I)
MODULE_REF_RE = re.compile(r"\bM(\d+)\b", re.I)
MISTAKE_RE = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*)$")

RECENT_ATTEMPTS = 10
MASTERED_MIN_ATTEMPTS = 5
MASTERED_ACCURACY = 0.85
MASTERED_RETENTION = 0.85
SHAKY_MIN_ATTEMPTS = 3
SHAKY_ACCURACY = 0.70
SHAKY_MIN_REVIEWS = 5
SHAKY_RETENTION = 0.80
SHAKY_OPEN_MISTAKES = 3

STATUS_ORDER = ["mastered", "shaky", "in progress", "not started"]


def module_key(number: str) -> str:
    return f"M{int(number)}"


def parse_syllabus(text: str) -> Dict[str, object]:
    title = None
    modules: List[Dict[str, str]] = []
    seen = set()
    for line in text.splitlines():
        if title is None and line.startswith("# "):
            match = TITLE_RE.match(line)
            if match:
                title = match.group(1)
            continue
        match = MODULE_HEADING_RE.match(line)
        if not match:
            continue
        # Only treat "## M1 ..." or "## Module 1 ..." as modules, not any numbered heading.
        head = line.lstrip("#").strip().lower()
        if not (head.startswith("m") and (head[1:2].isdigit() or head.startswith("module"))):
            continue
        key = module_key(match.group(1))
        if key in seen:
            continue
        seen.add(key)
        modules.append({"id": key, "title": match.group(2).strip() or key})
    return {"title": title, "modules": modules}


def read_quiz_log(path: Path) -> Tuple[Dict[str, List[dict]], int]:
    by_module: Dict[str, List[dict]] = {}
    bad = 0
    if not path.exists():
        return by_module, bad
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            ref = MODULE_REF_RE.search(str(entry["module"]))
            if not ref:
                raise ValueError("bad module")
            if "score" in entry:
                score = float(entry["score"])
            else:
                score = 1.0 if entry["correct"] else 0.0
            score = min(1.0, max(0.0, score))
        except (ValueError, KeyError, TypeError):
            bad += 1
            continue
        by_module.setdefault(module_key(ref.group(1)), []).append(
            {"date": str(entry.get("date", "")), "score": score})
    for entries in by_module.values():
        entries.sort(key=lambda e: e["date"])  # stable: keeps file order within a day
    return by_module, bad


def read_deck(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError:
        return []
    cards = data.get("cards", []) if isinstance(data, dict) else data
    return [c for c in cards if isinstance(c, dict)]


def card_modules(card: dict) -> List[str]:
    keys = []
    for tag in card.get("tags", []) or []:
        match = re.fullmatch(r"m(\d+)", str(tag).strip(), re.I)
        if match:
            keys.append(module_key(match.group(1)))
    return keys


def read_mistakes(path: Path) -> Dict[str, int]:
    open_counts: Dict[str, int] = {}
    if not path.exists():
        return open_counts
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        match = MISTAKE_RE.match(line)
        if not match or match.group(1).lower() == "x":
            continue
        ref = MODULE_REF_RE.search(match.group(2))
        if ref:
            key = module_key(ref.group(1))
            open_counts[key] = open_counts.get(key, 0) + 1
    return open_counts


def lessons_taught(folder: Path) -> set:
    taught = set()
    lessons = folder / "lessons"
    if lessons.is_dir():
        for f in lessons.iterdir():
            match = re.match(r"m(\d+)\b", f.name, re.I)
            if match and f.is_file():
                taught.add(module_key(match.group(1)))
    return taught


def classify(attempts: int, accuracy: Optional[float], reviews: int, retention: Optional[float],
             open_mistakes: int, lesson: bool) -> str:
    if not lesson and attempts == 0 and reviews == 0 and open_mistakes == 0:
        return "not started"
    if (attempts >= SHAKY_MIN_ATTEMPTS and accuracy is not None and accuracy < SHAKY_ACCURACY) \
            or (reviews >= SHAKY_MIN_REVIEWS and retention is not None and retention < SHAKY_RETENTION) \
            or open_mistakes >= SHAKY_OPEN_MISTAKES:
        return "shaky"
    if attempts >= MASTERED_MIN_ATTEMPTS and accuracy is not None and accuracy >= MASTERED_ACCURACY \
            and (retention is None or retention >= MASTERED_RETENTION) and open_mistakes == 0:
        return "mastered"
    return "in progress"


def build_report(folder: Path, today: dt.date) -> dict:
    syllabus_path = folder / "syllabus.md"
    if not syllabus_path.exists():
        raise FileNotFoundError(f"no syllabus.md in {folder} (run learn-syllabus first)")
    syllabus = parse_syllabus(syllabus_path.read_text(encoding="utf-8-sig"))
    quiz, bad_lines = read_quiz_log(folder / "quiz-log.jsonl")
    cards = read_deck(folder / "deck.json")
    mistakes = read_mistakes(folder / "mistakes.md")
    taught = lessons_taught(folder)
    t = today.isoformat()

    modules = []
    for module in syllabus["modules"]:
        key = module["id"]
        entries = quiz.get(key, [])
        recent = entries[-RECENT_ATTEMPTS:]
        accuracy = round(sum(e["score"] for e in recent) / len(recent), 3) if recent else None
        mod_cards = [c for c in cards if key in card_modules(c)]
        grades = [h.get("grade", 0) for c in mod_cards for h in c.get("history", []) or []]
        retention = round(sum(1 for g in grades if g >= 3) / len(grades), 3) if grades else None
        due = sum(1 for c in mod_cards if str(c.get("due", t)) <= t)
        status = classify(len(entries), accuracy, len(grades), retention, mistakes.get(key, 0), key in taught)
        modules.append({
            "id": key, "title": module["title"], "status": status, "lesson": key in taught,
            "attempts": len(entries), "accuracy": accuracy, "cards": len(mod_cards),
            "reviews": len(grades), "retention": retention, "due": due,
            "open_mistakes": mistakes.get(key, 0),
        })

    total_due = sum(1 for c in cards if str(c.get("due", t)) <= t)
    counts = {s: sum(1 for m in modules if m["status"] == s) for s in STATUS_ORDER}
    return {
        "topic": syllabus["title"] or folder.name,
        "today": t,
        "modules": modules,
        "counts": counts,
        "cards_due": total_due,
        "skipped_log_lines": bad_lines,
        "next": next_steps(modules, total_due),
    }


def next_steps(modules: List[dict], total_due: int) -> List[str]:
    steps: List[str] = []
    if total_due:
        steps.append(f"Review {total_due} due card{'s' if total_due != 1 else ''} first (learn-review). "
                     "Retrieval before new material.")
    shaky = sorted((m for m in modules if m["status"] == "shaky"),
                   key=lambda m: (m["accuracy"] if m["accuracy"] is not None else 1.0, m["id"]))
    for m in shaky:
        why = []
        if m["accuracy"] is not None and m["attempts"] >= SHAKY_MIN_ATTEMPTS and m["accuracy"] < SHAKY_ACCURACY:
            why.append(f"quiz accuracy {m['accuracy'] * 100:.0f}%")
        if m["retention"] is not None and m["reviews"] >= SHAKY_MIN_REVIEWS and m["retention"] < SHAKY_RETENTION:
            why.append(f"card retention {m['retention'] * 100:.0f}%")
        if m["open_mistakes"] >= SHAKY_OPEN_MISTAKES:
            why.append(f"{m['open_mistakes']} open mistakes")
        steps.append(f"Repair {m['id']} ({m['title']}): {', '.join(why)}. "
                     "Work the open mistakes with learn-tutor, then re-quiz with learn-quiz.")
    for m in modules:
        if m["status"] == "in progress" and m["attempts"] < MASTERED_MIN_ATTEMPTS:
            steps.append(f"Quiz {m['id']} ({m['title']}) with learn-quiz: only {m['attempts']} "
                         f"attempt{'s' if m['attempts'] != 1 else ''} logged, need {MASTERED_MIN_ATTEMPTS} to judge.")
    not_started = [m for m in modules if m["status"] == "not started"]
    if not_started:
        m = not_started[0]
        steps.append(f"Start {m['id']} ({m['title']}) with learn-lesson.")
    elif modules and all(m["status"] == "mastered" for m in modules):
        steps.append("Every module is mastered. Build the capstone project from syllabus.md.")
    return steps[:5]


def fmt_pct(value: Optional[float]) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def to_markdown(report: dict) -> str:
    c = report["counts"]
    lines = [
        f"# Progress: {report['topic']}",
        "",
        f"As of {report['today']}. {c['mastered']} mastered, {c['shaky']} shaky, "
        f"{c['in progress']} in progress, {c['not started']} not started. "
        f"{report['cards_due']} cards due.",
        "",
        "| Module | Status | Lesson | Quiz accuracy (last 10) | Attempts | Card retention | Cards due | Open mistakes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in report["modules"]:
        retention = fmt_pct(m["retention"])
        if m["reviews"]:
            retention += f" ({m['reviews']} reviews)"
        lesson = "yes" if m["lesson"] else "no"
        lines.append(
            f"| {m['id']}. {m['title']} | {m['status']} | {lesson} | {fmt_pct(m['accuracy'])} | "
            f"{m['attempts']} | {retention} | {m['due']} | {m['open_mistakes']} |")
    lines += ["", "## Next", ""]
    if report["next"]:
        lines += [f"{i}. {step}" for i, step in enumerate(report["next"], start=1)]
    else:
        lines.append("Nothing to suggest yet: add modules to syllabus.md.")
    lines += [
        "",
        "Rules: mastered = 5+ quiz attempts, 85%+ on the last 10, card retention 85%+, no open mistakes. "
        "Shaky = under 70% quiz accuracy, under 80% card retention, or 3+ open mistakes.",
    ]
    if report["skipped_log_lines"]:
        lines.append(f"\nNote: skipped {report['skipped_log_lines']} unreadable line(s) in quiz-log.jsonl.")
    return "\n".join(lines) + "\n"


def parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Classify each syllabus module as mastered / shaky / in progress / not started "
                    "from quiz-log.jsonl, deck.json, mistakes.md and lessons/.")
    parser.add_argument("folder", help="course folder, e.g. learn/python-decorators")
    parser.add_argument("--today", type=parse_date, default=None, help="date to report as (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    parser.add_argument("--out", help="also write the report to this file (e.g. progress.md)")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # never crash on a narrow console encoding
    try:
        report = build_report(Path(args.folder), args.today or dt.date.today())
    except (OSError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n" if args.json else to_markdown(report)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((text).encode("utf-8"))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
