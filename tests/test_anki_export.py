import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from _load import load

ax = load("skills/learn-flashcards/anki_export.py", "anki_export")

SAMPLE_MD = """# Cards: spaced repetition

Q: What does SM-2 adjust after every review?
A: The ease factor of the card.
Tags: m2 spacing

C: Spaced repetition schedules a review just before you would {{c1::forget}} it.
Extra: Forgetting curve.
Tags: m2

---

Q: Which Python keyword defines a generator?
A: yield
Tags: m3
"""


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ax.main(argv)
    return code, out.getvalue(), err.getvalue()


class ParseMarkdownTests(unittest.TestCase):
    def test_parses_basic_and_cloze_blocks(self):
        cards = ax.parse_markdown(SAMPLE_MD)
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0]["front"], "What does SM-2 adjust after every review?")
        self.assertEqual(cards[0]["back"], "The ease factor of the card.")
        self.assertEqual(cards[0]["tags"], "m2 spacing")
        self.assertIn("{{c1::forget}}", cards[1]["cloze"])
        self.assertEqual(cards[1]["extra"], "Forgetting curve.")

    def test_continuation_lines_and_fenced_code_with_blank_line(self):
        text = "Q: What does this print?\n```python\nprint(1)\n\nprint(2)\n```\nA: 1 then 2\non two lines\n"
        cards = ax.parse_markdown(text)
        self.assertEqual(len(cards), 1)
        self.assertIn("print(2)", cards[0]["front"])
        self.assertEqual(cards[0]["back"], "1 then 2\non two lines")

    def test_aliases_are_case_insensitive(self):
        cards = ax.parse_markdown("front: Capital of France?\nBACK: Paris\n")
        self.assertEqual(cards[0]["front"], "Capital of France?")
        self.assertEqual(cards[0]["back"], "Paris")

    def test_new_question_without_blank_line_starts_new_card(self):
        cards = ax.parse_markdown("Q: one?\nA: 1\nQ: two?\nA: 2\n")
        self.assertEqual([c["front"] for c in cards], ["one?", "two?"])

    def test_crlf_input(self):
        cards = ax.parse_markdown("Q: a?\r\nA: b\r\n\r\nQ: c?\r\nA: d\r\n")
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[1]["back"], "d")


class ParseJsonTests(unittest.TestCase):
    def test_list_and_object_forms(self):
        a = ax.parse_json('[{"front": "x?", "back": "y", "tags": ["m1"]}]')
        b = ax.parse_json('{"cards": [{"question": "x?", "answer": "y"}]}')
        self.assertEqual(a[0]["front"], "x?")
        self.assertEqual(b[0]["back"], "y")

    def test_cloze_roundtrip_from_normalized_json(self):
        raw = ax.parse_json('{"cards": [{"id": "c1", "kind": "cloze", "front": "A {{c1::b}}", "back": "note"}]}')
        self.assertEqual(raw[0]["cloze"], "A {{c1::b}}")
        self.assertEqual(raw[0]["extra"], "note")
        self.assertEqual(raw[0]["id"], "c1")

    def test_rejects_non_list(self):
        with self.assertRaises(ValueError):
            ax.parse_json('"nope"')


class ValidateTests(unittest.TestCase):
    def test_valid_sample_has_no_issues(self):
        cards, issues, dups = ax.validate(ax.parse_markdown(SAMPLE_MD))
        self.assertEqual(len(cards), 3)
        self.assertEqual(issues, [])
        self.assertEqual(dups, 0)

    def test_duplicates_are_merged_with_tag_union(self):
        raw = ax.parse_markdown("Q: What is 2+2?\nA: 4\nTags: m1\n\nQ: what is 2+2\nA: 4\nTags: arithmetic\n")
        cards, issues, dups = ax.validate(raw)
        self.assertEqual(len(cards), 1)
        self.assertEqual(dups, 1)
        self.assertEqual(cards[0]["tags"], ["m1", "arithmetic"])
        self.assertTrue(any("duplicate" in i.message for i in issues))

    def test_duplicate_with_different_answer_is_flagged(self):
        raw = ax.parse_markdown("Q: Year?\nA: 1990\n\nQ: Year?\nA: 1991\n")
        _, issues, _ = ax.validate(raw)
        self.assertTrue(any("answers differ" in i.message for i in issues))

    def test_errors_drop_cards(self):
        raw = ax.parse_markdown("Q: No answer here?\n\nA: orphan answer\n\nC: no deletion here\n\nQ: same\nA: same\n")
        cards, issues, _ = ax.validate(raw)
        self.assertEqual(cards, [])
        errors = [i for i in issues if i.level == "error"]
        self.assertEqual(len(errors), 4)

    def test_length_and_atomicity_warnings(self):
        raw = [{"line": 1, "front": "Q" * 250 + "?", "back": "x\ny\nz\nw"}]
        cards, issues, _ = ax.validate(raw, max_front=200, max_back=300)
        self.assertEqual(len(cards), 1)
        messages = " ".join(i.message for i in issues)
        self.assertIn("front is 251 chars", messages)
        self.assertIn("more than 3 lines", messages)
        self.assertTrue(all(i.level == "warning" for i in issues))

    def test_long_back_warning(self):
        _, issues, _ = ax.validate([{"line": 1, "front": "Why?", "back": "b" * 301}])
        self.assertTrue(any("back is 301 chars" in i.message for i in issues))

    def test_answer_leak_warning(self):
        _, issues, _ = ax.validate([{"line": 1, "front": "Is Paris the capital of France?", "back": "Paris"}])
        self.assertTrue(any("appears in the question" in i.message for i in issues))

    def test_too_many_cloze_deletions_warns(self):
        text = "{{c1::a}} {{c2::b}} {{c3::c}} {{c4::d}}"
        _, issues, _ = ax.validate([{"line": 1, "cloze": text}])
        self.assertTrue(any("4 cloze deletions" in i.message for i in issues))

    def test_ids_are_stable_and_extra_tags_added(self):
        raw = [{"line": 1, "front": "What is SM-2?", "back": "A scheduling algorithm", "tags": "m1"}]
        a, _, _ = ax.validate(raw, extra_tags=["srs topic"])
        b, _, _ = ax.validate([{"line": 9, "front": "what is  sm-2", "back": "other"}])
        self.assertEqual(a[0]["id"], b[0]["id"])
        self.assertTrue(a[0]["id"].startswith("c") and len(a[0]["id"]) == 9)
        self.assertEqual(a[0]["tags"], ["m1", "srs_topic"])  # spaces inside one tag become _


class OutputTests(unittest.TestCase):
    def test_tsv_escapes_html_tabs_and_newlines(self):
        cards = [{"id": "c1", "kind": "basic", "front": "List<int>\tsize?", "back": "a\nb", "tags": ["m1", "x"]}]
        tsv = ax.to_tsv(cards, "basic")
        lines = tsv.splitlines()
        self.assertEqual(lines[0], "#separator:tab")
        self.assertIn("#notetype:Basic", lines)
        self.assertEqual(lines[-1], "List&lt;int&gt;    size?\ta<br>b\tm1 x")
        self.assertEqual(lines[-1].count("\t"), 2)

    def test_no_headers(self):
        cards = [{"id": "c1", "kind": "basic", "front": "f", "back": "b", "tags": []}]
        self.assertEqual(ax.to_tsv(cards, "basic", headers=False), "f\tb\t\n")


class CliTests(unittest.TestCase):
    def test_end_to_end_writes_basic_cloze_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cards.md"
            src.write_text(SAMPLE_MD, encoding="utf-8")
            code, out, err = run_cli([str(src), "--json-out", str(Path(tmp) / "cards.json"), "--tag", "srs"])
            self.assertEqual(code, 0, err)
            basic = (Path(tmp) / "anki-basic.tsv").read_text(encoding="utf-8").splitlines()
            cloze = (Path(tmp) / "anki-cloze.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len([l for l in basic if not l.startswith("#")]), 2)
            self.assertIn("#notetype:Cloze", cloze)
            self.assertTrue(cloze[-1].endswith("\tm2 srs"))
            data = json.loads((Path(tmp) / "cards.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["cards"]), 3)
            self.assertEqual({c["kind"] for c in data["cards"]}, {"basic", "cloze"})
            self.assertIn("3 kept (2 basic, 1 cloze)", out)

    def test_errors_exit_1_and_check_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cards.md"
            src.write_text("Q: lonely question?\n", encoding="utf-8")
            code, _, err = run_cli([str(src), "--check"])
            self.assertEqual(code, 1)
            self.assertIn("empty back", err)
            self.assertFalse((Path(tmp) / "anki-basic.tsv").exists())

    def test_strict_fails_on_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cards.json"
            src.write_text(json.dumps([{"front": "Q?", "back": "a\nb\nc\nd"}]), encoding="utf-8")
            self.assertEqual(run_cli([str(src), "--check"])[0], 0)
            self.assertEqual(run_cli([str(src), "--check", "--strict"])[0], 1)

    def test_missing_file_exit_2(self):
        code, _, err = run_cli(["does-not-exist.md", "--check"])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_bad_json_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cards.json"
            src.write_text("{not json", encoding="utf-8")
            self.assertEqual(run_cli([str(src)])[0], 2)


if __name__ == "__main__":
    unittest.main()
