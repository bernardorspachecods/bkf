import re
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PLAN_TESTS = TESTS.parents[1] / "skills" / "agentic-work" / "tests"

# A line that puts a fake executable named codex on disk: the path is built from "codex" and made executable.
FAKE_CODEX = re.compile(r"""/\s*["']codex["']""")
EXCLUDED = {"hermetic.py", "test_hermetic.py"}


def unpinned_fake_codex_files(folders):
    """Test files that create a fake codex executable but neither pin the backend nor mention HARNESS_BACKEND."""
    found = []
    for folder in folders:
        for path in sorted(folder.glob("*.py")):
            if path.name in EXCLUDED:
                continue
            text = path.read_text(encoding="utf-8")
            if not FAKE_CODEX.search(text) or "chmod(" not in text:
                continue
            if "pin_backend(" in text or "HARNESS_BACKEND" in text:
                continue
            found.append(str(path))
    return found


class HermeticTests(unittest.TestCase):
    def test_every_fake_codex_test_pins_the_backend(self):
        self.assertEqual(unpinned_fake_codex_files([TESTS, PLAN_TESTS]), [])


if __name__ == "__main__":
    unittest.main()
