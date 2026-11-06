#!/usr/bin/env python3
"""Spaced repetition over a JSON deck using the SM-2 algorithm.

Commands
--------
  srs.py deck.json add cards.json        add new cards / refresh text of known ones
  srs.py deck.json due [--limit N]       list cards due today (fronts only)
  srs.py deck.json show <id>             print one card, front and back
  srs.py deck.json grade <id> <0-5>      record a review and reschedule
  srs.py deck.json stats                 deck health: new, learning, mature, retention

Every command accepts --today YYYY-MM-DD so runs are reproducible. Without it
the local date is used. Card ids may be shortened to any unique prefix.

SM-2 (as published by P. Wozniak, 1987; ease update as in the common
Wikipedia formulation):
  grade q in 0..5, where q >= 3 counts as a successful recall
  if q >= 3:  reps 0 -> interval 1, reps 1 -> interval 6,
              else interval = ceil(interval * ease); reps += 1
  else:       reps = 0, interval = 1, lapses += 1
  ease += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02);  ease >= 1.3
  due = today + interval

Deck format: {"version": 1, "cards": [{"id", "kind", "front", "back", "tags",
"ease", "interval", "reps", "lapses", "due", "last_review", "history"}]}
Standard library only, no network.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MATURE_DAYS = 21
LEECH_LAPSES = 4
RETENTION_WINDOW_DAYS = 30
CLOZE_RE = re.compile(r"\{\{c\d+::(.+?)(?:::(.*?))?\}\}", re.S)


class DeckError(Exception):
    """Raised for user-facing problems (bad id, bad grade, unreadable deck)."""


# --------------------------------------------------------------------------- dates


def parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def iso(day: dt.date) -> str:
    return day.isoformat()


# --------------------------------------------------------------------------- core algorithm


def new_schedule(today: dt.date) -> dict:
    return {"ease": DEFAULT_EASE, "interval": 0, "reps": 0, "lapses": 0,
            "due": iso(today), "last_review": None, "history": []}


def sm2(card: dict, grade: int, today: dt.date) -> dict:
    """Return a new card dict rescheduled after a review with the given grade (0-5)."""
    if isinstance(grade, bool) or not isinstance(grade, int) or not 0 <= grade <= 5:
        raise DeckError(f"grade must be an integer 0-5, got {grade!r}")
    out = dict(card)
    ease = float(card.get("ease", DEFAULT_EASE))
    interval = int(card.get("interval", 0))
    reps = int(card.get("reps", 0))
    lapses = int(card.get("lapses", 0))

    if grade >= 3:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, math.ceil(interval * ease - 1e-9))
        reps += 1
    else:
        reps = 0
        interval = 1
        lapses += 1

    ease = ease + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ease = max(MIN_EASE, round(ease, 4))

    out.update({
        "ease": ease,
        "interval": interval,
        "reps": reps,
        "lapses": lapses,
        "due": iso(today + dt.timedelta(days=interval)),
        "last_review": iso(today),
        "history": list(card.get("history", [])) + [{"date": iso(today), "grade": grade}],
    })
    return out


# --------------------------------------------------------------------------- deck io


def empty_deck() -> dict:
    return {"version": 1, "cards": []}


def load_deck(path: Path, create: bool = False) -> dict:
    if not path.exists():
        if create:
            return empty_deck()
        raise DeckError(f"deck not found: {path} (create it with the 'add' command)")
    try:
        deck = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise DeckError(f"cannot read deck {path}: {exc}") from exc
    if isinstance(deck, list):
        deck = {"version": 1, "cards": deck}
    if not isinstance(deck, dict) or not isinstance(deck.get("cards"), list):
        raise DeckError(f"{path} is not a deck (expected an object with a 'cards' list)")
    return deck


def save_deck(path: Path, deck: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes((json.dumps(deck, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    os.replace(tmp, path)


def find_card(deck: dict, card_id: str) -> dict:
    cards = deck["cards"]
    exact = [c for c in cards if c.get("id") == card_id]
    if exact:
        return exact[0]
    matches = [c for c in cards if str(c.get("id", "")).startswith(card_id)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise DeckError(f"no card with id {card_id!r}")
    raise DeckError(f"id prefix {card_id!r} is ambiguous: " + ", ".join(c["id"] for c in matches[:5]))


def add_cards(deck: dict, incoming: List[dict], today: dt.date) -> Dict[str, int]:
    """Merge cards into the deck. New ids get a fresh schedule; known ids keep theirs."""
    counts = {"added": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    by_id = {c["id"]: c for c in deck["cards"] if "id" in c}
    for item in incoming:
        if not isinstance(item, dict) or not item.get("id") or not item.get("front"):
            counts["skipped"] += 1
            continue
        content = {
            "kind": item.get("kind", "basic"),
            "front": str(item["front"]),
            "back": str(item.get("back", "")),
            "tags": list(item.get("tags", [])),
        }
        existing = by_id.get(item["id"])
        if existing is None:
            card = {"id": item["id"], **content, **new_schedule(today)}
            deck["cards"].append(card)
            by_id[card["id"]] = card
            counts["added"] += 1
        elif any(existing.get(k) != v for k, v in content.items()):
            existing.update(content)
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    return counts


# --------------------------------------------------------------------------- queries


def due_cards(deck: dict, today: dt.date, limit: Optional[int] = None) -> List[dict]:
    due = [c for c in deck["cards"] if c.get("due", iso(today)) <= iso(today)]
    # Overdue reviewed cards first (oldest due date), then new cards, stable by id.
    due.sort(key=lambda c: (c.get("due", ""), 1 if not c.get("history") else 0, c.get("id", "")))
    return due[:limit] if limit else due


def masked_front(card: dict) -> str:
    if card.get("kind") == "cloze":
        return CLOZE_RE.sub(lambda m: f"[{m.group(2)}]" if m.group(2) else "[...]", card["front"])
    return card["front"]


def full_answer(card: dict) -> str:
    if card.get("kind") == "cloze":
        text = CLOZE_RE.sub(lambda m: m.group(1), card["front"])
        return text + (f"\n\n{card['back']}" if card.get("back") else "")
    return card.get("back", "")


def deck_stats(deck: dict, today: dt.date) -> dict:
    cards = deck["cards"]
    t = iso(today)
    week = iso(today + dt.timedelta(days=7))
    window_start = iso(today - dt.timedelta(days=RETENTION_WINDOW_DAYS))
    reviewed = [c for c in cards if c.get("history")]
    recent = [h for c in cards for h in c.get("history", []) if window_start < h["date"] <= t]
    all_grades = [h for c in cards for h in c.get("history", [])]

    def retention(entries):
        if not entries:
            return None
        return round(sum(1 for h in entries if h["grade"] >= 3) / len(entries), 3)

    return {
        "today": t,
        "total": len(cards),
        "new": sum(1 for c in cards if not c.get("history")),
        "learning": sum(1 for c in reviewed if int(c.get("interval", 0)) < MATURE_DAYS),
        "mature": sum(1 for c in reviewed if int(c.get("interval", 0)) >= MATURE_DAYS),
        "due_today": sum(1 for c in cards if c.get("due", t) <= t),
        "overdue": sum(1 for c in reviewed if c.get("due", t) < t),
        "due_next_7_days": sum(1 for c in cards if t < c.get("due", t) <= week),
        "reviews_total": len(all_grades),
        "reviews_last_30_days": len(recent),
        "retention_last_30_days": retention(recent),
        "retention_all_time": retention(all_grades),
        "average_ease": round(sum(float(c.get("ease", DEFAULT_EASE)) for c in reviewed) / len(reviewed), 2)
        if reviewed else None,
        "leeches": sorted(c["id"] for c in cards if int(c.get("lapses", 0)) >= LEECH_LAPSES),
    }


def format_stats(s: dict) -> str:
    def pct(v):
        return "n/a" if v is None else f"{v * 100:.0f}%"

    lines = [
        f"Deck stats as of {s['today']}",
        f"  cards:      {s['total']} total | {s['new']} new | {s['learning']} learning | {s['mature']} mature (interval >= {MATURE_DAYS}d)",
        f"  due:        {s['due_today']} today ({s['overdue']} overdue) | {s['due_next_7_days']} more in the next 7 days",
        f"  reviews:    {s['reviews_total']} total | {s['reviews_last_30_days']} in the last 30 days",
        f"  retention:  {pct(s['retention_last_30_days'])} last 30 days | {pct(s['retention_all_time'])} all time",
        f"  avg ease:   {s['average_ease'] if s['average_ease'] is not None else 'n/a'}",
        f"  leeches:    {', '.join(s['leeches']) if s['leeches'] else 'none'} (lapsed {LEECH_LAPSES}+ times)",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SM-2 spaced repetition over a JSON deck. Deterministic with --today.")
    parser.add_argument("deck", help="path to deck.json")
    parser.add_argument("--today", type=parse_date, default=None,
                        help="treat this date (YYYY-MM-DD) as today; default is the local date")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--today", type=parse_date, default=argparse.SUPPRESS,
                        help="treat this date (YYYY-MM-DD) as today")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", parents=[common], help="add cards from a JSON file (e.g. anki_export.py --json-out)")
    p_add.add_argument("cards", help="cards JSON: a list or {\"cards\": [...]} with id/front/back/tags")

    p_due = sub.add_parser("due", parents=[common], help="list cards due today")
    p_due.add_argument("--limit", type=int, default=None, help="show at most N cards")
    p_due.add_argument("--json", action="store_true", help="machine-readable output")
    p_due.add_argument("--show-back", action="store_true", help="include answers (not for quizzing)")

    p_show = sub.add_parser("show", parents=[common], help="print one card with its answer")
    p_show.add_argument("id")

    p_grade = sub.add_parser("grade", parents=[common], help="record a review: 0-2 forgot, 3 hard, 4 good, 5 easy")
    p_grade.add_argument("id")
    p_grade.add_argument("grade", type=int)
    p_grade.add_argument("--force", action="store_true",
                         help="allow a second grade for the same card on the same day")

    p_stats = sub.add_parser("stats", parents=[common], help="deck health summary")
    p_stats.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # never crash on a narrow console encoding
    today = args.today or dt.date.today()
    path = Path(args.deck)
    try:
        if args.command == "add":
            deck = load_deck(path, create=True)
            try:
                data = json.loads(Path(args.cards).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise DeckError(f"cannot read cards {args.cards}: {exc}") from exc
            incoming = data.get("cards", []) if isinstance(data, dict) else data
            counts = add_cards(deck, incoming, today)
            save_deck(path, deck)
            print(f"added {counts['added']}, updated {counts['updated']}, unchanged {counts['unchanged']}, "
                  f"skipped {counts['skipped']} -> {path} ({len(deck['cards'])} cards)")
            return 0

        deck = load_deck(path)
        if args.command == "due":
            cards = due_cards(deck, today, args.limit)
            total_due = len(due_cards(deck, today))
            if args.json:
                rows = [{"id": c["id"], "front": masked_front(c), "tags": c.get("tags", []),
                         "due": c.get("due"), "new": not c.get("history"),
                         **({"back": full_answer(c)} if args.show_back else {})} for c in cards]
                print(json.dumps({"today": iso(today), "due": total_due, "cards": rows}, indent=2,
                                 ensure_ascii=False))
                return 0
            print(f"{total_due} due on {iso(today)} (deck has {len(deck['cards'])} cards)"
                  + (f"; showing {len(cards)}" if len(cards) < total_due else ""))
            for c in cards:
                tag = f" [{' '.join(c.get('tags', []))}]" if c.get("tags") else ""
                label = "new" if not c.get("history") else f"due {c.get('due')}"
                print(f"{c['id']}  ({label}){tag}  {masked_front(c)}")
                if args.show_back:
                    print(f"    -> {full_answer(c)}")
            return 0

        if args.command == "show":
            c = find_card(deck, args.id)
            print(f"{c['id']}  ease {c.get('ease')}  interval {c.get('interval')}d  due {c.get('due')}")
            print(f"Q: {masked_front(c)}")
            print(f"A: {full_answer(c)}")
            return 0

        if args.command == "grade":
            card = find_card(deck, args.id)
            if card.get("last_review") == iso(today) and not args.force:
                raise DeckError(f"{card['id']} was already graded on {iso(today)}; "
                                "SM-2 expects one grade per day (use --force to override)")
            early = card.get("due", iso(today)) > iso(today)
            updated = sm2(card, args.grade, today)
            index = deck["cards"].index(card)
            deck["cards"][index] = updated
            save_deck(path, deck)
            note = " (reviewed before it was due)" if early else ""
            print(f"{updated['id']}: grade {args.grade} -> next review {updated['due']} "
                  f"(in {updated['interval']}d, ease {updated['ease']}, reps {updated['reps']}){note}")
            return 0

        if args.command == "stats":
            s = deck_stats(deck, today)
            print(json.dumps(s, indent=2) if args.json else format_stats(s))
            return 0
    except DeckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
