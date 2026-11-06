import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path

from _load import load

pg = load("skills/learn-progress/progress.py", "progress")

D = dt.date(2026, 11, 7)

SYLLABUS = """# Syllabus: Python decorators

Level: beginner

## M1. Functions are objects
## M2: Closures
## Module 3 - Writing decorators
## M4 — functools.wraps
## Capstone
## 5. Not a module
"""


def log_lines(module, results, date="2026-11-0{}"):
    lines = []
    for i, ok in enumerate(results, start=1):
        lines.append(json.dumps({"date": date.format(i % 7 + 1), "module": module, "correct": ok}))
    return lines


class ParseTests(unittest.TestCase):
    def test_parse_syllabus(self):
        s = pg.parse_syllabus(SYLLABUS)
        self.assertEqual(s["title"], "Python decorators")
        self.assertEqual([m["id"] for m in s["modules"]], ["M1", "M2", "M3", "M4"])
        self.assertEqual(s["modules"][2]["title"], "Writing decorators")
        self.assertEqual(s["modules"][3]["title"], "functools.wraps")

    def test_classify_rules(self):
        self.assertEqual(pg.classify(0, None, 0, None, 0, False), "not started")
        self.assertEqual(pg.classify(0, None, 0, None, 0, True), "in progress")
        self.assertEqual(pg.classify(5, 0.9, 0, None, 0, True), "mastered")
        self.assertEqual(pg.classify(5, 0.9, 10, 0.9, 1, True), "in progress")
        self.assertEqual(pg.classify(5, 0.9, 10, 0.7, 0, True), "shaky")
        self.assertEqual(pg.classify(3, 0.5, 0, None, 0, True), "shaky")
        self.assertEqual(pg.classify(2, 0.0, 0, None, 0, True), "in progress")
        self.assertEqual(pg.classify(1, 1.0, 0, None, 3, False), "shaky")
        self.assertEqual(pg.classify(4, 1.0, 0, None, 0, True), "in progress")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "python-decorators"
        (self.dir / "lessons").mkdir(parents=True)
        (self.dir / "syllabus.md").write_text(SYLLABUS, encoding="utf-8")
        for name in ("m1-functions-are-objects.md", "m2-closures.md", "m3-writing.md"):
            (self.dir / "lessons" / name).write_text("lesson", encoding="utf-8")
        lines = (log_lines("M1", [True] * 6)
                 + log_lines("M2", [False, True, False, False])
                 + log_lines("m3", [True, True])
                 + ["not json", json.dumps({"module": "M1"})])
        (self.dir / "quiz-log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.dir / "mistakes.md").write_text(
            "# Mistakes\n\n- [ ] 2026-11-05 · M2 · q2 · confused closure with scope\n"
            "- [x] 2026-11-04 · M1 · q1 · fixed\n- [ ] 2026-11-06 · M3 · q4 · forgot to return wrapper\n",
            encoding="utf-8")
        deck = {"cards": [
            {"id": "a", "tags": ["m1"], "due": "2026-11-20", "history": [{"date": "2026-11-01", "grade": 5}] * 5},
            {"id": "b", "tags": ["m3"], "due": "2026-11-07", "history": [{"date": "2026-11-01", "grade": 4}]},
            {"id": "c", "tags": ["m4"], "due": "2026-11-07", "history": []},
        ]}
        (self.dir / "deck.json").write_text(json.dumps(deck), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_report(self):
        r = pg.build_report(self.dir, D)
        status = {m["id"]: m["status"] for m in r["modules"]}
        self.assertEqual(status, {"M1": "mastered", "M2": "shaky", "M3": "in progress", "M4": "not started"})
        m2 = r["modules"][1]
        self.assertEqual((m2["attempts"], m2["accuracy"], m2["open_mistakes"]), (4, 0.25, 1))
        self.assertEqual(r["cards_due"], 2)
        self.assertEqual(r["skipped_log_lines"], 2)
        self.assertEqual(r["counts"], {"mastered": 1, "shaky": 1, "in progress": 1, "not started": 1})
        self.assertTrue(r["next"][0].startswith("Review 2 due cards"))
        self.assertIn("Repair M2", r["next"][1])
        self.assertIn("Quiz M3", r["next"][2])
        self.assertIn("Start M4", r["next"][-1])

    def test_card_due_card_without_history_does_not_start_module(self):
        r = pg.build_report(self.dir, D)
        m4 = r["modules"][3]
        self.assertEqual((m4["cards"], m4["reviews"], m4["due"]), (1, 0, 1))

    def test_partial_scores_and_last_ten_window(self):
        entries = [json.dumps({"date": "2026-10-01", "module": "M4", "score": 0.0})] * 5
        entries += [json.dumps({"date": "2026-11-01", "module": "M4", "score": 1})] * 10
        (self.dir / "quiz-log.jsonl").write_text("\n".join(entries), encoding="utf-8")
        r = pg.build_report(self.dir, D)
        m4 = r["modules"][3]
        self.assertEqual((m4["attempts"], m4["accuracy"]), (15, 1.0))

    def test_all_mastered_suggests_capstone(self):
        (self.dir / "syllabus.md").write_text("# Syllabus: T\n\n## M1. Only\n", encoding="utf-8")
        (self.dir / "mistakes.md").write_text("", encoding="utf-8")
        (self.dir / "deck.json").write_text('{"cards": []}', encoding="utf-8")
        r = pg.build_report(self.dir, D)
        self.assertEqual(r["modules"][0]["status"], "mastered")
        self.assertIn("capstone", r["next"][-1])

    def test_markdown_and_cli(self):
        out_file = self.dir / "progress.md"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pg.main([str(self.dir), "--today", "2026-11-07", "--out", str(out_file)])
        self.assertEqual(code, 0)
        text = out_file.read_text(encoding="utf-8")
        self.assertEqual(text, buf.getvalue())
        self.assertIn("# Progress: Python decorators", text)
        self.assertIn("| M2. Closures | shaky | yes | 25% | 4 |", text)
        self.assertIn("| M1. Functions are objects | mastered | yes | 100% | 6 | 100% (5 reviews)", text)
        self.assertIn("## Next", text)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pg.main([str(self.dir), "--today", "2026-11-07", "--json"])
        self.assertEqual(json.loads(buf.getvalue())["today"], "2026-11-07")

    def test_missing_syllabus_exit_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pg.main([str(Path(self.tmp.name) / "nothing")]), 2)


if __name__ == "__main__":
    unittest.main()
