"""Structure checks for the plugin: skills, agents, manifests, README, LICENSE."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPO_NAME = "learn-anything-skill"
SKILLS = sorted(p for p in (REPO / "skills").iterdir() if p.is_dir())
AGENTS = sorted((REPO / "agents").glob("*.md"))
SCRIPTS = sorted((REPO / "skills").glob("*/*.py"))


def frontmatter(path: Path) -> dict:
    """Parse simple YAML frontmatter by hand: key: value, and folded '>-' blocks."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            key, value = match.group(1), match.group(2).strip()
            if value in (">", ">-", "|", "|-"):
                data[key] = ""
            else:
                data[key] = value.strip('"').strip("'")
        elif key is not None and line.strip():
            data[key] = (data[key] + " " + line.strip()).strip()
    return {}  # no closing ---


class SkillTests(unittest.TestCase):
    def test_has_seven_or_eight_skills_with_prefix(self):
        self.assertTrue(7 <= len(SKILLS) <= 8, [p.name for p in SKILLS])
        for skill in SKILLS:
            self.assertTrue(skill.name.startswith("learn-"), skill.name)

    def test_skill_frontmatter(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                md = skill / "SKILL.md"
                self.assertTrue(md.exists(), f"{md} missing")
                fm = frontmatter(md)
                self.assertEqual(fm.get("name"), skill.name)
                self.assertRegex(fm["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
                description = fm.get("description", "")
                self.assertTrue(description, "description is empty")
                self.assertLess(len(description), 1024, "description too long")
                self.assertIn("Use when", description)

    def test_skill_body_size_and_sections(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                count = len(text.splitlines())
                self.assertTrue(60 <= count <= 200, f"{count} lines")
                self.assertIn("What NOT to do", text)

    def test_referenced_scripts_exist(self):
        for skill in SKILLS:
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            for ref in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+\.py)", text):
                with self.subTest(skill=skill.name, ref=ref):
                    self.assertTrue((skill / ref).resolve().exists(), f"{ref} not found")


class AgentTests(unittest.TestCase):
    def test_expected_agents(self):
        self.assertEqual({p.stem for p in AGENTS}, {"socratic-tutor", "quiz-master", "explainer"})

    def test_agent_frontmatter(self):
        for agent in AGENTS:
            with self.subTest(agent=agent.name):
                fm = frontmatter(agent)
                self.assertEqual(fm.get("name"), agent.stem)
                self.assertTrue(fm.get("description"))
                self.assertTrue(fm.get("tools"))
                count = len(agent.read_text(encoding="utf-8").splitlines())
                self.assertTrue(40 <= count <= 120, f"{count} lines")

    def test_read_only_agents_cannot_write(self):
        for name in ("socratic-tutor", "explainer"):
            tools = frontmatter(REPO / "agents" / f"{name}.md")["tools"]
            self.assertNotIn("Write", tools)
            self.assertNotIn("Edit", tools)


class ManifestTests(unittest.TestCase):
    def load(self, name):
        return json.loads((REPO / ".claude-plugin" / name).read_text(encoding="utf-8"))

    def test_marketplace(self):
        data = self.load("marketplace.json")
        self.assertEqual(data["name"], REPO_NAME)
        self.assertEqual(REPO.name, REPO_NAME)
        self.assertEqual(data["owner"]["name"], "Vivek Bhange")
        self.assertEqual(len(data["plugins"]), 1)
        plugin = data["plugins"][0]
        self.assertEqual(plugin["name"], REPO_NAME)
        self.assertEqual(plugin["source"], "./")
        self.assertEqual(plugin["homepage"], f"https://github.com/vivekbhange-hub/{REPO_NAME}")

    def test_plugin(self):
        data = self.load("plugin.json")
        self.assertEqual(data["name"], REPO_NAME)
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["license"], "MIT")
        self.assertEqual(data["author"]["name"], "Vivek Bhange")
        self.assertEqual(data["repository"], f"https://github.com/vivekbhange-hub/{REPO_NAME}")
        self.assertTrue(6 <= len(data["keywords"]) <= 10)
        for kw in ("claude-code", "claude-skills"):
            self.assertIn(kw, data["keywords"])


class DocsTests(unittest.TestCase):
    def test_readme_mentions_every_skill_and_agent(self):
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        for skill in SKILLS:
            self.assertIn(skill.name, readme)
        for agent in AGENTS:
            self.assertIn(agent.stem, readme)
        self.assertIn(f"/plugin marketplace add vivekbhange-hub/{REPO_NAME}", readme)

    def test_license_is_mit(self):
        text = (REPO / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT", text)
        self.assertIn("Copyright (c) 2026 Vivek Bhange", text)

    def test_other_files(self):
        for name in ("CONTRIBUTING.md", "CHANGELOG.md", ".gitignore"):
            self.assertTrue((REPO / name).exists(), name)
        self.assertIn("2026-11-07", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"))


class ScriptTests(unittest.TestCase):
    def test_every_script_has_tests_and_help(self):
        self.assertTrue(SCRIPTS)
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertTrue((REPO / "tests" / f"test_{script.stem}.py").exists())
                result = subprocess.run([sys.executable, str(script), "--help"],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage", result.stdout.lower())

    def test_scripts_use_standard_library_only(self):
        allowed = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}
        if not allowed - {"__future__"}:
            self.skipTest("sys.stdlib_module_names needs Python 3.10+")
        for script in SCRIPTS:
            text = script.read_text(encoding="utf-8")
            for module in re.findall(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", text, re.M):
                with self.subTest(script=script.name, module=module):
                    self.assertIn(module, allowed)


if __name__ == "__main__":
    unittest.main()
