#!/usr/bin/env python3
"""Turn a flashcard file (Markdown or JSON) into Anki-importable TSV files.

Input formats
-------------
Markdown (cards.md): one card per block, blocks separated by a blank line.

    Q: What does SM-2 adjust after every review?
    A: The ease factor of the card.
    Tags: m2 spacing

    C: Spaced repetition schedules a review just before you would {{c1::forget}} it.
    Extra: Optional note shown on the back.
    Tags: m2

Keys are case-insensitive: Q/Front, A/Back, C/Cloze, Extra, Tags, ID.
Lines that do not start with a key continue the previous field. Fenced code
blocks may contain blank lines. Headings, "---" rules and HTML comments
between cards are ignored.

JSON: a list of cards or {"cards": [...]}. Each card has front/back
(or question/answer), or cloze/text plus optional extra; tags may be a list or
a space-separated string; id is optional.

Output
------
anki-basic.tsv  front<TAB>back<TAB>tags   (note type: Basic)
anki-cloze.tsv  text<TAB>extra<TAB>tags   (note type: Cloze, only if needed)
cards.json      normalized cards with stable ids (with --json-out), which
                srs.py can import.

Exit codes: 0 clean, 1 card errors (or warnings with --strict), 2 usage/IO.
Standard library only, no network.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_MAX_FRONT = 200
DEFAULT_MAX_BACK = 300
MAX_BACK_LINES = 3
MAX_CLOZE_DELETIONS = 3

CLOZE_RE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.*?))?\}\}", re.S)
KEY_RE = re.compile(r"^(q|front|a|back|c|cloze|extra|tags|id)\s*:\s?(.*)$", re.I)
KEY_ALIASES = {
    "q": "front", "front": "front",
    "a": "back", "back": "back",
    "c": "cloze", "cloze": "cloze",
    "extra": "extra", "tags": "tags", "id": "id",
}
IGNORED_LINE_RE = re.compile(r"^(#{1,6}\s.*|-{3,}|\*{3,}|<!--.*-->)\s*$")


class Issue:
    """A validation problem tied to a card."""

    def __init__(self, level: str, where: str, message: str):
        self.level = level  # "error" or "warning"
        self.where = where
        self.message = message

    def __str__(self) -> str:
        return f"{self.level.upper()} {self.where}: {self.message}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Issue({self.level!r}, {self.where!r}, {self.message!r})"


def normalize_key(text: str) -> str:
    """Key used for duplicate detection and ids: case/space/punctuation-insensitive."""
    key = re.sub(r"\s+", " ", text).strip().casefold()
    return key.rstrip(" ?.!:;")


def card_id(kind: str, text: str) -> str:
    digest = hashlib.sha1(f"{kind}|{normalize_key(text)}".encode("utf-8")).hexdigest()
    return "c" + digest[:8]


def split_tags(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[\s,]+", value)
    else:
        parts = [str(v) for v in value]
    tags: List[str] = []
    for part in parts:
        tag = re.sub(r"\s+", "_", part.strip().lstrip("#"))
        if tag and tag not in tags:
            tags.append(tag)
    return tags


# --------------------------------------------------------------------------- parsing


def parse_markdown(text: str) -> List[dict]:
    """Parse the cards.md block format into raw card dicts (with a 'line' field)."""
    cards: List[dict] = []
    current: Optional[dict] = None
    field: Optional[str] = None
    in_fence = False

    def finish():
        nonlocal current, field
        if current is not None:
            for key in ("front", "back", "cloze", "extra"):
                if key in current:
                    current[key] = current[key].strip("\n").rstrip()
            cards.append(current)
        current, field = None, None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if current is not None and field is not None:
                current[field] += ("\n" if current[field] else "") + line
            continue
        if in_fence:
            if current is not None and field is not None:
                current[field] += "\n" + line
            continue
        if not line.strip():
            finish()
            continue
        match = KEY_RE.match(line)
        if match:
            key = KEY_ALIASES[match.group(1).lower()]
            value = match.group(2).strip()
            if current is None:
                current = {"line": lineno}
            if key in ("front", "cloze") and ("front" in current or "cloze" in current):
                # A new question without a blank line in between starts a new card.
                finish()
                current = {"line": lineno}
            current[key] = value
            field = key if key in ("front", "back", "cloze", "extra") else None
            continue
        if current is None:
            if IGNORED_LINE_RE.match(line.strip()):
                continue
            current = {"line": lineno, "_stray": line.strip()}
            field = None
            continue
        if field is not None:
            current[field] += ("\n" if current[field] else "") + line
        else:
            current.setdefault("_stray", line.strip())
    finish()
    return cards


def parse_json(text: str) -> List[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("cards", [])
    if not isinstance(data, list):
        raise ValueError("JSON input must be a list of cards or an object with a 'cards' list")
    cards: List[dict] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            cards.append({"line": index, "_stray": repr(item)[:60]})
            continue
        card: dict = {"line": index}
        kind = str(item.get("kind", "")).lower()
        front = item.get("front", item.get("question"))
        cloze = item.get("cloze", item.get("text"))
        if kind == "cloze" and cloze is None:
            cloze = front
        if cloze is not None and (kind == "cloze" or front is None):
            card["cloze"] = str(cloze)
            extra = item.get("extra", item.get("back") if kind == "cloze" else None)
            if extra:
                card["extra"] = str(extra)
        if front is not None and "cloze" not in card:
            card["front"] = str(front)
        back = item.get("back", item.get("answer"))
        if back is not None and "cloze" not in card:
            card["back"] = str(back)
        if "tags" in item:
            card["tags"] = item["tags"]
        if item.get("id"):
            card["id"] = str(item["id"])
        cards.append(card)
    return cards


# --------------------------------------------------------------------------- validation


def _body_lines(text: str) -> int:
    lines, in_fence = 0, False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if line.strip() and not in_fence:
            lines += 1
    return lines


def validate(raw_cards: List[dict], max_front: int = DEFAULT_MAX_FRONT,
             max_back: int = DEFAULT_MAX_BACK, extra_tags: Optional[List[str]] = None
             ) -> Tuple[List[dict], List[Issue], int]:
    """Validate and deduplicate. Returns (cards, issues, duplicates_merged)."""
    extra_tags = extra_tags or []
    issues: List[Issue] = []
    kept: List[dict] = []
    seen: Dict[Tuple[str, str], dict] = {}
    duplicates = 0

    for raw in raw_cards:
        where = f"card at line {raw.get('line', '?')}"
        if "_stray" in raw and not any(k in raw for k in ("front", "cloze")):
            issues.append(Issue("error", where, f"no 'Q:' or 'C:' line found near: {raw['_stray']!r}"))
            continue
        tags = split_tags(raw.get("tags")) + [t for t in split_tags(extra_tags)]
        tags = list(dict.fromkeys(tags))

        if "cloze" in raw:
            kind = "cloze"
            front = raw["cloze"].strip()
            back = raw.get("extra", "").strip()
            if not front:
                issues.append(Issue("error", where, "empty cloze text"))
                continue
            deletions = {m.group(1) for m in CLOZE_RE.finditer(front)}
            if not deletions:
                issues.append(Issue("error", where, "cloze card has no {{c1::...}} deletion"))
                continue
            if len(deletions) > MAX_CLOZE_DELETIONS:
                issues.append(Issue("warning", where,
                                    f"{len(deletions)} cloze deletions; keep it to one idea per card"))
            visible = CLOZE_RE.sub(lambda m: m.group(2), front)
            if len(visible) > max_front:
                issues.append(Issue("warning", where,
                                    f"cloze text is {len(visible)} chars (limit {max_front}); split it"))
        else:
            kind = "basic"
            front = raw.get("front", "").strip()
            back = raw.get("back", "").strip()
            if not front:
                issues.append(Issue("error", where, "empty front (question)"))
                continue
            if not back:
                issues.append(Issue("error", where, "empty back (answer)"))
                continue
            if normalize_key(front) == normalize_key(back):
                issues.append(Issue("error", where, "front and back are identical"))
                continue
            if len(front) > max_front:
                issues.append(Issue("warning", where,
                                    f"front is {len(front)} chars (limit {max_front}); ask one thing"))
            if len(back) > max_back:
                issues.append(Issue("warning", where,
                                    f"back is {len(back)} chars (limit {max_back}); one fact per card"))
            if _body_lines(back) > MAX_BACK_LINES:
                issues.append(Issue("warning", where,
                                    "back has more than 3 lines; looks like a list, split it or use cloze"))
            if len(back) >= 4 and normalize_key(back) in normalize_key(front):
                issues.append(Issue("warning", where, "the answer appears in the question"))

        key = (kind, normalize_key(front))
        if key in seen:
            first = seen[key]
            duplicates += 1
            for tag in tags:
                if tag not in first["tags"]:
                    first["tags"].append(tag)
            note = f"duplicate of card at line {first['line']}; merged tags"
            if normalize_key(back) != normalize_key(first["back"]):
                note += " (answers differ, kept the first)"
            issues.append(Issue("warning", where, note))
            continue

        card = {
            "id": raw.get("id") or card_id(kind, front),
            "kind": kind,
            "front": front,
            "back": back,
            "tags": tags,
            "line": raw.get("line"),
        }
        seen[key] = card
        kept.append(card)
    return kept, issues, duplicates


# --------------------------------------------------------------------------- output


def tsv_field(text: str) -> str:
    text = html.escape(text, quote=False)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    return text.replace("\n", "<br>")


def to_tsv(cards: List[dict], kind: str, headers: bool = True) -> str:
    rows: List[str] = []
    if headers:
        rows.append("#separator:tab")
        rows.append("#html:true")
        rows.append("#notetype:" + ("Cloze" if kind == "cloze" else "Basic"))
        rows.append("#tags column:3")
    for card in cards:
        if card["kind"] != kind:
            continue
        rows.append("\t".join([tsv_field(card["front"]), tsv_field(card["back"]), " ".join(card["tags"])]))
    return "\n".join(rows) + "\n"


def to_json(cards: List[dict]) -> str:
    clean = [{k: c[k] for k in ("id", "kind", "front", "back", "tags")} for c in cards]
    return json.dumps({"cards": clean}, indent=2, ensure_ascii=False) + "\n"


def read_input(path: str, fmt: str) -> Tuple[str, str]:
    if path == "-":
        text = sys.stdin.read()
    else:
        text = Path(path).read_text(encoding="utf-8-sig")
    if fmt == "auto":
        if path.lower().endswith(".json") or text.lstrip().startswith(("[", "{")):
            fmt = "json"
        else:
            fmt = "md"
    return text, fmt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert flashcards (Markdown or JSON) into Anki-importable TSV "
                    "(front, back, tags). Deduplicates and checks that cards are atomic.")
    parser.add_argument("input", help="cards.md or cards.json ('-' reads stdin)")
    parser.add_argument("--format", choices=["auto", "md", "json"], default="auto",
                        help="input format (default: guess from extension/content)")
    parser.add_argument("--out-dir", help="where to write anki-basic.tsv / anki-cloze.tsv "
                                          "(default: the input file's folder)")
    parser.add_argument("--json-out", help="also write normalized cards with stable ids to this JSON file")
    parser.add_argument("--tag", action="append", default=[],
                        help="extra tag added to every card (repeatable), e.g. the topic slug")
    parser.add_argument("--max-front", type=int, default=DEFAULT_MAX_FRONT,
                        help=f"warn when a front is longer than this (default {DEFAULT_MAX_FRONT})")
    parser.add_argument("--max-back", type=int, default=DEFAULT_MAX_BACK,
                        help=f"warn when a back is longer than this (default {DEFAULT_MAX_BACK})")
    parser.add_argument("--no-headers", action="store_true",
                        help="omit the '#separator:tab' style header lines (for Anki before 2.1.55)")
    parser.add_argument("--check", action="store_true", help="validate only, write nothing")
    parser.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # never crash on a narrow console encoding
    try:
        text, fmt = read_input(args.input, args.format)
        raw = parse_json(text) if fmt == "json" else parse_markdown(text)
    except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
        print(f"error: cannot read {args.input}: {exc}", file=sys.stderr)
        return 2

    cards, issues, duplicates = validate(raw, args.max_front, args.max_back, args.tag)
    for issue in issues:
        print(issue, file=sys.stderr)
    errors = sum(1 for i in issues if i.level == "error")
    warnings = len(issues) - errors
    basic = sum(1 for c in cards if c["kind"] == "basic")
    cloze = len(cards) - basic

    summary = (f"{len(raw)} cards read: {len(cards)} kept ({basic} basic, {cloze} cloze), "
               f"{duplicates} duplicates merged, {errors} errors, {warnings} warnings.")
    if not args.check:
        if args.out_dir:
            out_dir = Path(args.out_dir)
        elif args.input == "-":
            out_dir = Path.cwd()
        else:
            out_dir = Path(args.input).resolve().parent
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        if basic or not cloze:
            target = out_dir / "anki-basic.tsv"
            target.write_bytes((to_tsv(cards, "basic", not args.no_headers)).encode("utf-8"))
            written.append(f"{basic} -> {target}")
        if cloze:
            target = out_dir / "anki-cloze.tsv"
            target.write_bytes((to_tsv(cards, "cloze", not args.no_headers)).encode("utf-8"))
            written.append(f"{cloze} -> {target}")
        if args.json_out:
            target = Path(args.json_out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((to_json(cards)).encode("utf-8"))
            written.append(f"json -> {target}")
        summary += " Wrote " + "; ".join(written) + "."
    print(summary)
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
