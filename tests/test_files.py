import os
import shutil
import tempfile
import unittest

from pydiff.diff import diff_files, diff_trees, read_lines


def write(path, content):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return path


class TempDirsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydiff_test_")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make(self, name, content):
        path = os.path.join(self.tmp, name)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        return write(path, content)


class ReadLinesTest(TempDirsTest):
    def test_trailing_newline_not_an_extra_line(self):
        a = self.make("a.txt", "one\ntwo\n")
        self.assertEqual(read_lines(a), ["one", "two"])

    def test_no_trailing_newline(self):
        a = self.make("a.txt", "one\ntwo")
        self.assertEqual(read_lines(a), ["one", "two"])

    def test_empty_file(self):
        a = self.make("a.txt", "")
        self.assertEqual(read_lines(a), [])

    def test_single_empty_line(self):
        a = self.make("a.txt", "\n")
        self.assertEqual(read_lines(a), [""])

    def test_crlf_preserved_without_flag(self):
        a = self.make("a.txt", "one\r\ntwo\r\n")
        self.assertEqual(read_lines(a), ["one\r", "two\r"])

    def test_strip_trailing_cr(self):
        a = self.make("a.txt", "one\r\ntwo\r\n")
        self.assertEqual(read_lines(a, strip_trailing_cr=True), ["one", "two"])

    def test_ignore_case(self):
        a = self.make("a.txt", "Hello\nWORLD\n")
        self.assertEqual(read_lines(a, ignore_case=True), ["hello", "world"])


class DiffFilesTest(TempDirsTest):
    def test_identical_files_empty_output(self):
        a = self.make("a.txt", "one\ntwo\nthree\n")
        b = self.make("b.txt", "one\ntwo\nthree\n")
        self.assertEqual(diff_files(a, b), "")

    def test_empty_vs_empty(self):
        a = self.make("a.txt", "")
        b = self.make("b.txt", "")
        self.assertEqual(diff_files(a, b), "")

    def test_differing_files(self):
        a = self.make("a.txt", "one\ntwo\nthree\n")
        b = self.make("b.txt", "one\nTWO\nthree\n")
        out = diff_files(a, b)
        self.assertIn("--- ", out)
        self.assertIn("+++ ", out)
        self.assertIn("@@ -1,3 +1,3 @@", out)
        self.assertIn("-two", out)
        self.assertIn("+TWO", out)

    def test_ignore_case_flag(self):
        a = self.make("a.txt", "Hello\nWorld\n")
        b = self.make("b.txt", "hello\nworld\n")
        # Without the flag the files differ...
        self.assertNotEqual(diff_files(a, b), "")
        # ...with it they are identical.
        self.assertEqual(diff_files(a, b, ignore_case=True), "")

    def test_strip_trailing_cr_flag(self):
        a = self.make("a.txt", "one\r\ntwo\r\n")
        b = self.make("b.txt", "one\ntwo\n")
        self.assertNotEqual(diff_files(a, b), "")
        self.assertEqual(diff_files(a, b, strip_trailing_cr=True), "")

    def test_filename_headers_use_given_paths(self):
        a = self.make("a.txt", "x\n")
        b = self.make("b.txt", "y\n")
        out = diff_files(a, b)
        lines = out.splitlines()
        self.assertEqual(lines[0], "--- " + a)
        self.assertEqual(lines[1], "+++ " + b)

    def test_single_changed_character_of_line(self):
        a = self.make("a.txt", "greetings\nfoobar\n")
        b = self.make("b.txt", "greetings\nfoobar!\n")
        expected = (
            "--- %s\n"
            "+++ %s\n"
            "@@ -1,2 +1,2 @@\n"
            " greetings\n"
            "-foobar\n"
            "+foobar!\n"
        ) % (a, b)
        self.assertEqual(diff_files(a, b), expected)


class DiffTreesTest(TempDirsTest):
    def setUp(self):
        super().setUp()
        self.dir_a = os.path.join(self.tmp, "a")
        self.dir_b = os.path.join(self.tmp, "b")
        os.makedirs(self.dir_a)
        os.makedirs(self.dir_b)

    def test_identical_trees(self):
        for d in (self.dir_a, self.dir_b):
            write(os.path.join(d, "same.txt"), "x\ny\n")
            os.makedirs(os.path.join(d, "sub"))
            write(os.path.join(d, "sub", "nested.txt"), "1\n2\n")
        self.assertEqual(diff_trees(self.dir_a, self.dir_b), "")

    def test_changed_common_file(self):
        write(os.path.join(self.dir_a, "f.txt"), "a\nb\n")
        write(os.path.join(self.dir_b, "f.txt"), "a\nB\n")
        out = diff_trees(self.dir_a, self.dir_b)
        self.assertIn("@@ -1,2 +1,2 @@", out)
        self.assertIn("-b", out)
        self.assertIn("+B", out)

    def test_only_in_a(self):
        write(os.path.join(self.dir_a, "extra.txt"), "x\n")
        write(os.path.join(self.dir_a, "common.txt"), "c\n")
        write(os.path.join(self.dir_b, "common.txt"), "c\n")
        out = diff_trees(self.dir_a, self.dir_b)
        self.assertIn("Only in %s: extra.txt" % self.dir_a, out)
        self.assertNotIn("Only in %s" % self.dir_b, out)

    def test_only_in_b_and_nested(self):
        write(os.path.join(self.dir_b, "new.txt"), "x\n")
        os.makedirs(os.path.join(self.dir_a, "sub"))
        write(os.path.join(self.dir_a, "sub", "gone.txt"), "x\n")
        out = diff_trees(self.dir_a, self.dir_b)
        self.assertIn("Only in %s: new.txt" % self.dir_b, out)
        self.assertIn(
            "Only in %s: gone.txt" % os.path.join(self.dir_a, "sub"), out
        )

    def test_common_changed_added_removed_combined(self):
        # common+changed
        write(os.path.join(self.dir_a, "common.txt"), "1\n2\n3\n")
        write(os.path.join(self.dir_b, "common.txt"), "1\nCHANGED\n3\n")
        # only in a
        write(os.path.join(self.dir_a, "only-a.txt"), "a\n")
        # only in b
        write(os.path.join(self.dir_b, "only-b.txt"), "b\n")
        # identical file
        write(os.path.join(self.dir_a, "same.txt"), "z\n")
        write(os.path.join(self.dir_b, "same.txt"), "z\n")

        out = diff_trees(self.dir_a, self.dir_b)
        self.assertIn("--- %s" % os.path.join(self.dir_a, "common.txt"), out)
        self.assertIn("-2", out)
        self.assertIn("+CHANGED", out)
        self.assertIn("Only in %s: only-a.txt" % self.dir_a, out)
        self.assertIn("Only in %s: only-b.txt" % self.dir_b, out)
        self.assertNotIn("same.txt", out)
        self.assertNotIn("-z", out)

    def test_trees_equal_empty(self):
        self.assertEqual(diff_trees(self.dir_a, self.dir_b), "")

    def test_recursive_changed_outside_root(self):
        os.makedirs(os.path.join(self.dir_a, "sub1"))
        write(os.path.join(self.dir_a, "sub1", "deep.txt"), "a\n")
        os.makedirs(os.path.join(self.dir_b, "sub1"))
        write(os.path.join(self.dir_b, "sub1", "deep.txt"), "b\n")
        out = diff_trees(self.dir_a, self.dir_b)
        self.assertIn("@@ -1 +1 @@", out)
        self.assertIn("-a", out)
        self.assertIn("+b", out)


if __name__ == "__main__":
    unittest.main()