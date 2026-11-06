import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path

from _load import load

srs = load("skills/learn-review/srs.py", "srs")

D = dt.date(2026, 11, 7)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = srs.main(argv)
    return code, out.getvalue(), err.getvalue()


def fresh(card_id="c1", **extra):
    card = {"id": card_id, "kind": "basic", "front": f"front {card_id}", "back": "back", "tags": ["m1"]}
    card.update(srs.new_schedule(D))
    card.update(extra)
    return card


class Sm2Tests(unittest.TestCase):
    def test_first_three_successes_follow_1_6_ceil_ease(self):
        c = srs.sm2(fresh(), 4, D)
        self.assertEqual((c["interval"], c["reps"], c["ease"]), (1, 1, 2.5))
        self.assertEqual(c["due"], "2026-11-08")
        c = srs.sm2(c, 4, D + dt.timedelta(days=1))
        self.assertEqual((c["interval"], c["reps"]), (6, 2))
        c = srs.sm2(c, 4, D + dt.timedelta(days=7))
        self.assertEqual((c["interval"], c["reps"]), (15, 3))  # ceil(6 * 2.5)
        self.assertEqual(c["due"], "2026-11-29")

    def test_ease_changes_by_grade(self):
        self.assertAlmostEqual(srs.sm2(fresh(), 5, D)["ease"], 2.6)
        self.assertAlmostEqual(srs.sm2(fresh(), 4, D)["ease"], 2.5)
        self.assertAlmostEqual(srs.sm2(fresh(), 3, D)["ease"], 2.36)
        self.assertAlmostEqual(srs.sm2(fresh(), 0, D)["ease"], 1.7)

    def test_ease_floor(self):
        c = fresh(ease=1.35)
        self.assertEqual(srs.sm2(c, 0, D)["ease"], 1.3)

    def test_interval_uses_old_ease_and_rounds_up(self):
        c = fresh(ease=2.36, interval=6, reps=2)
        out = srs.sm2(c, 3, D)
        self.assertEqual(out["interval"], 15)  # ceil(6 * 2.36 = 14.16)
        self.assertAlmostEqual(out["ease"], 2.22)

    def test_failure_resets_reps_and_counts_lapse(self):
        c = fresh(ease=2.5, interval=40, reps=5, lapses=1)
        out = srs.sm2(c, 2, D)
        self.assertEqual((out["reps"], out["interval"], out["lapses"]), (0, 1, 2))
        self.assertEqual(out["due"], "2026-11-08")
        self.assertEqual(out["history"][-1], {"date": "2026-11-07", "grade": 2})

    def test_does_not_mutate_input(self):
        c = fresh()
        srs.sm2(c, 5, D)
        self.assertEqual(c["reps"], 0)
        self.assertEqual(c["history"], [])

    def test_invalid_grades(self):
        for bad in (-1, 6, 3.5, True, "4"):
            with self.assertRaises(srs.DeckError):
                srs.sm2(fresh(), bad, D)


class DeckTests(unittest.TestCase):
    def test_add_merges_without_resetting_schedule(self):
        deck = srs.empty_deck()
        counts = srs.add_cards(deck, [{"id": "c1", "front": "a?", "back": "b"}, {"front": "no id"}], D)
        self.assertEqual(counts, {"added": 1, "updated": 0, "unchanged": 0, "skipped": 1})
        deck["cards"][0] = srs.sm2(deck["cards"][0], 5, D)
        counts = srs.add_cards(deck, [{"id": "c1", "front": "a?", "back": "better b", "kind": "basic", "tags": []}],
                               D + dt.timedelta(days=3))
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(deck["cards"][0]["back"], "better b")
        self.assertEqual(deck["cards"][0]["reps"], 1)

    def test_due_order_and_limit(self):
        deck = {"cards": [
            fresh("new1"),
            fresh("late", due="2026-11-01", history=[{"date": "2026-10-31", "grade": 4}]),
            fresh("future", due="2026-11-20", history=[{"date": "2026-11-01", "grade": 5}]),
            fresh("today", due="2026-11-07", history=[{"date": "2026-11-01", "grade": 4}]),
        ]}
        ids = [c["id"] for c in srs.due_cards(deck, D)]
        self.assertEqual(ids, ["late", "today", "new1"])
        self.assertEqual(len(srs.due_cards(deck, D, limit=1)), 1)

    def test_find_card_by_prefix(self):
        deck = {"cards": [fresh("cabc123"), fresh("cabd456")]}
        self.assertEqual(srs.find_card(deck, "cabc")["id"], "cabc123")
        with self.assertRaises(srs.DeckError):
            srs.find_card(deck, "cab")
        with self.assertRaises(srs.DeckError):
            srs.find_card(deck, "zzz")

    def test_cloze_masking(self):
        card = fresh(kind="cloze", front="Reviews come before you {{c1::forget}} and {{c2::fade::verb}}.", back="")
        self.assertEqual(srs.masked_front(card), "Reviews come before you [...] and [verb].")
        self.assertEqual(srs.full_answer(card), "Reviews come before you forget and fade.")

    def test_stats(self):
        deck = {"cards": [
            fresh("n"),
            fresh("m", interval=30, due="2026-12-01", lapses=4,
                  history=[{"date": "2026-11-01", "grade": 4}, {"date": "2026-09-01", "grade": 1}]),
            fresh("l", interval=6, due="2026-11-10", ease=2.3, history=[{"date": "2026-11-04", "grade": 2}]),
        ]}
        s = srs.deck_stats(deck, D)
        self.assertEqual((s["total"], s["new"], s["learning"], s["mature"]), (3, 1, 1, 1))
        self.assertEqual(s["due_today"], 1)
        self.assertEqual(s["due_next_7_days"], 1)
        self.assertEqual(s["reviews_last_30_days"], 2)
        self.assertEqual(s["retention_last_30_days"], 0.5)
        self.assertAlmostEqual(s["retention_all_time"], 0.333)
        self.assertEqual(s["average_ease"], 2.4)
        self.assertEqual(s["leeches"], ["m"])

    def test_stats_empty_deck(self):
        s = srs.deck_stats(srs.empty_deck(), D)
        self.assertIsNone(s["retention_last_30_days"])
        self.assertIsNone(s["average_ease"])
        self.assertIn("n/a", srs.format_stats(s))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.deck = self.dir / "deck.json"
        cards = {"cards": [
            {"id": "c11111111", "kind": "basic", "front": "What is retrieval practice?",
             "back": "Recalling from memory", "tags": ["m1"]},
            {"id": "c22222222", "kind": "cloze", "front": "Space reviews to beat the {{c1::forgetting curve}}.",
             "back": "", "tags": ["m2"]},
        ]}
        (self.dir / "cards.json").write_text(json.dumps(cards), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_cycle_is_deterministic(self):
        code, out, _ = run_cli([str(self.deck), "--today", "2026-11-07", "add", str(self.dir / "cards.json")])
        self.assertEqual(code, 0)
        self.assertIn("added 2", out)

        code, out, _ = run_cli([str(self.deck), "due", "--today", "2026-11-07"])
        self.assertIn("2 due on 2026-11-07", out)
        self.assertIn("[...]", out)
        self.assertNotIn("Recalling from memory", out)

        code, out, _ = run_cli([str(self.deck), "grade", "c111", "5", "--today", "2026-11-07"])
        self.assertEqual(code, 0)
        self.assertIn("next review 2026-11-08", out)

        code, out, _ = run_cli([str(self.deck), "--today", "2026-11-07", "due", "--json"])
        data = json.loads(out)
        self.assertEqual(data["due"], 1)
        self.assertEqual(data["cards"][0]["id"], "c22222222")

        code, _, err = run_cli([str(self.deck), "--today", "2026-11-07", "grade", "c11111111", "4"])
        self.assertEqual(code, 2)
        self.assertIn("already graded", err)

        code, out, _ = run_cli([str(self.deck), "--today", "2026-11-07", "grade", "c11111111", "4", "--force"])
        self.assertEqual(code, 0)
        self.assertIn("reviewed before it was due", out)

        code, out, _ = run_cli([str(self.deck), "--today", "2026-11-07", "stats", "--json"])
        stats = json.loads(out)
        self.assertEqual(stats["reviews_total"], 2)
        self.assertEqual(stats["new"], 1)

        saved = json.loads(self.deck.read_text(encoding="utf-8"))
        self.assertEqual(saved["cards"][0]["history"][0], {"date": "2026-11-07", "grade": 5})
        self.assertFalse((self.dir / "deck.json.tmp").exists())

    def test_show_and_errors(self):
        run_cli([str(self.deck), "--today", "2026-11-07", "add", str(self.dir / "cards.json")])
        code, out, _ = run_cli([str(self.deck), "show", "c2"])
        self.assertIn("A: Space reviews to beat the forgetting curve.", out)
        self.assertEqual(run_cli([str(self.deck), "grade", "nope", "3"])[0], 2)
        self.assertEqual(run_cli([str(self.deck), "grade", "c1", "9"])[0], 2)
        self.assertEqual(run_cli([str(self.dir / "missing.json"), "due"])[0], 2)

    def test_bad_date_is_rejected(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                srs.main([str(self.deck), "--today", "11/07/2026", "due"])


if __name__ == "__main__":
    unittest.main()
