import sys
import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_modes
from agent_modes import bash_is_readonly


class GitStash(unittest.TestCase):
    def test_stash_that_moves_changes_is_detected(self):
        for command in [
            "git stash", "git stash -q 2>/dev/null; echo '(not stashing - skip)'", "git stash pop",
            "git stash push -m x", "git -C /repo stash", "ls && git stash apply", "git stash drop", "git stash clear",
            "git stash $(", 
        ]:
            with self.subTest(command=command):
                self.assertTrue(agent_modes.git_stash_writes(command))

    def test_other_commands_are_not(self):
        for command in [
            "git stash list", "git stash show -p", "git -C r stash list", 'echo "git stash"',
            "git status", "grep stash f", "git log --stat",
        ]:
            with self.subTest(command=command):
                self.assertFalse(agent_modes.git_stash_writes(command))

    def test_hook_denies_in_every_mode(self):
        data = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s-none",
                "tool_input": {"command": "git stash"}}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            agent_modes.on_tool(data)
        self.assertIn("deny", out.getvalue())


class ReadonlyBash(unittest.TestCase):
    def check(self, commands, expected):
        for command in commands:
            with self.subTest(command=command):
                self.assertIs(bash_is_readonly(command), expected)

    def test_exploration_is_allowed(self):
        self.check([
            "ls -la",
            "cd /a/b && cat MAP.md | head -40; echo ----; ls ../x | head",
            "grep -rn foo . 2>/dev/null",
            "rg foo > /dev/null",
            "ls nope 2>&1 | head",
            "cat $(git rev-parse --show-toplevel)/MAP.md",
            "git -C /repo log --oneline | head",
            "git status && git diff HEAD~1",
            "git branch", "git branch -a", "git stash list", "git config --get user.name",
            "git worktree list", "git remote -v",
            "gh pr view 12", "gh issue list",
            "gh api repos/o/r/contents/f.md --jq .content | base64 -d",
            "gh api -X GET /x", "gh api --method GET /x", "gh api /x -H 'Accept: a' --paginate",
            "bkf validate .", "bkf inventory .", "bkf search foo",
            "sed -n 1,20p f", "awk '{print $1}' f", "test -f x && echo yes",
            "find . -name '*.py'", "sort f | uniq -c",
            "cat <<'EOF'\nhello\nEOF",
        ], True)

    def test_writes_are_blocked(self):
        self.check([
            "echo hi > f.txt", "echo hi >> f.txt", "cat a | tee b", "ls &> out",
            "rm -rf x", "mv a b", "cp a b", "mkdir d", "touch f", "chmod +x f",
            "git commit -m a", "git add .", "git push", "git checkout main",
            "git branch newbranch", "git branch -D old", "git tag v1", "git stash",
            "git stash pop", "git config user.name x", "git remote add o url",
            "git worktree add ../w", "git reset --hard",
            "gh pr create", "gh pr merge 1", "gh api -X POST /x",
            "gh api --method=DELETE /x", "gh api -XPATCH /x", "gh api /x -f a=b", "gh api /x -F a=b",
            "gh api /x --input body.json", "gh api graphql -f query=q",
            "bkf inventory . --write", "bkf sync .",
            "sed -i s/a/b/ f", "find . -delete", "find . -exec rm {} +",
            "sort -o out in", "awk 'BEGIN{system(\"rm x\")}'", "awk '{print > \"f\"}' in",
            "cat $(rm -rf x)", "cd x && rm y", "python3 script.py", "npm install",
            "ls; rm x", "ls && touch x", "ls | xargs rm",
        ], False)

    def test_quoted_shell_syntax_is_not_split_or_treated_as_a_redirect(self):
        self.check([
            'grep -E "a|b" file',
            "rg 'foo|bar' .",
            'echo "a > b"',
            "echo 'x; rm y'",
            'grep "x" file | head',
            "echo '$(rm x)'",
            'cat "my file.md"',
        ], True)

    def test_unquoted_shell_syntax_and_unsafe_substitutions_are_blocked(self):
        self.check([
            "ls; rm x",
            'grep "x" file | rm y',
            "echo a > b",
            'echo "a" > b',
            'echo "$(rm x)"',
            'echo "`rm x`"',
            "cat <(rm x)",
            'echo "abc',
            "ls && touch x",
            "cat a | tee b",
        ], False)


class FailureOutput(unittest.TestCase):
    def test_invalid_input_is_reported_and_does_not_raise(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(agent_modes.sys, "stdin", io.StringIO("not json")):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                agent_modes.main()
        output = json.loads(stdout.getvalue())
        self.assertIn("systemMessage", output)
        self.assertIn("modes failed", output["systemMessage"])
        self.assertIn(output["systemMessage"], stderr.getvalue())


class PromptModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        patcher = patch.object(agent_modes, "STATE_DIR", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_hook(self, data):
        stdout = io.StringIO()
        with patch.object(agent_modes.sys, "stdin", io.StringIO(json.dumps(data))):
            with contextlib.redirect_stdout(stdout):
                agent_modes.main()
        return stdout.getvalue()

    def prompt(self, value):
        return self.run_hook({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": value})

    def test_w_injects_implement_and_stores_mode(self):
        output = self.prompt("w: build it")
        self.assertIn("MODE: IMPLEMENT", output)
        self.assertIn("'w:'", output)
        self.assertEqual(json.loads(agent_modes.state_file("s").read_text())["mode"], "w")

    def test_t_injects_talk_and_blocks_mutating_tool(self):
        output = self.prompt("t: discuss this")
        self.assertIn("MODE: TALK / BRAINSTORM", output)
        self.assertEqual(json.loads(agent_modes.state_file("s").read_text())["mode"], "t")
        blocked = self.run_hook({"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Write"})
        decision = json.loads(blocked)
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_uppercase_prefixes_work(self):
        self.assertIn("MODE: IMPLEMENT", self.prompt("W: implement"))
        self.assertEqual(json.loads(agent_modes.state_file("s").read_text())["mode"], "w")
        self.assertIn("MODE: TALK / BRAINSTORM", self.prompt("T: talk"))
        self.assertEqual(json.loads(agent_modes.state_file("s").read_text())["mode"], "t")

    def test_i_and_n_are_free_and_clear_saved_mode(self):
        for prefix in ("i:", "n:"):
            with self.subTest(prefix=prefix):
                path = agent_modes.state_file("s")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"mode":"t"}')
                self.assertEqual(self.prompt(prefix + " idea or implement"), "")
                self.assertFalse(path.exists())

    def test_other_prompt_text_does_not_match(self):
        for prompt in ("wait: x", "Tell me"):
            with self.subTest(prompt=prompt):
                path = agent_modes.state_file("s")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{"mode":"t"}')
                self.assertEqual(self.prompt(prompt), "")
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
