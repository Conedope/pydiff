import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(args, cwd=None):
    proc = subprocess.run(
        [sys.executable, "-m", "pydiff.cli"] + args,
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
    )
    return proc.returncode, proc.stdout, proc.stderr


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydiff_cli_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make(self, name, content):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return path

    # ---- exit codes ----

    def test_identical_files_exit_zero(self):
        a = self.make("a.txt", "same\ntext\n")
        b = self.make("b.txt", "same\ntext\n")
        code, out, err = run_cli([a, b])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")

    def test_differing_files_exit_one(self):
        a = self.make("a.txt", "one\n")
        b = self.make("b.txt", "two\n")
        code, out, err = run_cli([a, b])
        self.assertEqual(code, 1)
        self.assertIn("--- %s" % a, out)
        self.assertIn("+++ %s" % b, out)
        self.assertIn("@@ -1 +1 @@", out)

    def test_missing_file_exit_two(self):
        code, out, err = run_cli(["/nonexistent/a.txt", "/nonexistent/b.txt"])
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_error_goes_to_stderr(self):
        a = self.make("a.txt", "x\n")
        code, out, err = run_cli([a, "/nonexistent/x.txt"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_directory_without_recursive_exit_two(self):
        code, out, err = run_cli([self.tmp, self.tmp])
        self.assertEqual(code, 2)

    # ---- modes and flags ----

    def test_recursive_directory_mode_exit_one(self):
        da = os.path.join(self.tmp, "da")
        db = os.path.join(self.tmp, "db")
        os.makedirs(da)
        os.makedirs(db)
        with open(os.path.join(da, "f.txt"), "w") as f:
            f.write("a\n")
        with open(os.path.join(db, "f.txt"), "w") as f:
            f.write("b\n")
        with open(os.path.join(db, "extra.txt"), "w") as f:
            f.write("x\n")
        code, out, err = run_cli(["-r", da, db])
        self.assertEqual(code, 1, err)
        self.assertIn("@@ -1 +1 @@", out)
        self.assertIn("Only in %s: extra.txt" % db, out)

    def test_recursive_identical_dirs_exit_zero(self):
        da = os.path.join(self.tmp, "da")
        db = os.path.join(self.tmp, "db")
        os.makedirs(da)
        os.makedirs(db)
        for d in (da, db):
            with open(os.path.join(d, "f.txt"), "w") as f:
                f.write("same\n")
        code, out, err = run_cli(["-r", da, db])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")

    def test_context_flag(self):
        a = self.make("a.txt", "1\n2\n3\n4\n5\n")
        b = self.make("b.txt", "1\n2\nCHANGED\n4\n5\n")
        code, out, err = run_cli(["-c", "0", a, b])
        self.assertEqual(code, 1)
        self.assertIn("@@ -3 +3 @@", out)

    def test_ignore_case_flag(self):
        a = self.make("a.txt", "Hello\n")
        b = self.make("b.txt", "hello\n")
        code, _, _ = run_cli(["--ignore-case", a, b])
        self.assertEqual(code, 0)
        code2, _, _ = run_cli([a, b])
        self.assertEqual(code2, 1)

    def test_strip_trailing_cr_flag(self):
        a = self.make("a.txt", "hello\r\n")
        b = self.make("b.txt", "hello\n")
        code, _, _ = run_cli(["--strip-trailing-cr", a, b])
        self.assertEqual(code, 0)
        code2, _, _ = run_cli([a, b])
        self.assertEqual(code2, 1)

    def test_unified_flag_is_accepted(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["-u", a, b])
        self.assertEqual(code, 1)
        self.assertIn("--- ", out)

    # ---- color handling ----

    def test_color_always_emits_escapes(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["--color", "always", a, b])
        self.assertEqual(code, 1)
        self.assertIn("\x1b[31m", out)
        self.assertIn("\x1b[32m", out)

    def test_bare_color_means_always(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["--color", a, b])
        self.assertEqual(code, 1)
        self.assertIn("\x1b[31m", out)

    def test_no_color_emits_no_escapes(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["--no-color", a, b])
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)

    def test_color_never_emits_no_escapes(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["--color", "never", a, b])
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)

    def test_color_auto_in_pipe_emits_no_escapes(self):
        # subprocess stdout is a pipe, so auto must not colorize.
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        code, out, _ = run_cli(["--color", "auto", a, b])
        self.assertEqual(code, 1)
        self.assertNotIn("\x1b", out)

    # ---- meta ----

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("pydiff 1.0.0", out)

    def test_help(self):
        code, out, _ = run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("OLD", out)
        self.assertIn("NEW", out)
        self.assertIn("--recursive", out)

    def test_same_file_twice_exit_zero(self):
        a = self.make("a.txt", "x\n")
        code, out, _ = run_cli([a, a])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_unicode_content_roundtrip(self):
        a = self.make("a.txt", "caf\u00e9\n\u4e2d\u6587\n")
        b = self.make("b.txt", "caf\u00e9\n\u4e2d\u6587s\n")
        code, out, _ = run_cli([a, b])
        self.assertEqual(code, 1)
        self.assertIn("-" + "\u4e2d\u6587", out)
        self.assertIn("+" + "\u4e2d\u6587s", out)


if __name__ == "__main__":
    unittest.main()