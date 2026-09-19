import unittest

from pydiff.diff import myers_diff, to_unified

F = "old.txt"
T = "new.txt"


def unify(a, b, context=3, fromfile=F, tofile=T):
    return to_unified(a, b, myers_diff(a, b), fromfile, tofile, context)


class ToUnifiedTest(unittest.TestCase):
    def test_identical_returns_empty(self):
        self.assertEqual(unify(["a", "b"], ["a", "b"]), "")
        self.assertEqual(unify([], []), "")

    def test_middle_change(self):
        a = ["one", "two", "three", "four", "five", "six", "seven"]
        b = ["one", "two", "THREE", "four", "five", "six", "seven"]
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,6 +1,6 @@\n"
            " one\n"
            " two\n"
            "-three\n"
            "+THREE\n"
            " four\n"
            " five\n"
            " six\n"
        )
        self.assertEqual(unify(a, b), expected)

    def test_empty_old_vs_nonempty(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -0,0 +1,2 @@\n"
            "+alpha\n"
            "+beta\n"
        )
        self.assertEqual(unify([], ["alpha", "beta"]), expected)

    def test_nonempty_old_vs_empty(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,2 +0,0 @@\n"
            "-alpha\n"
            "-beta\n"
        )
        self.assertEqual(unify(["alpha", "beta"], []), expected)

    def test_insertion_only_at_start(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,3 +1,5 @@\n"
            "+n1\n"
            "+n2\n"
            " l1\n"
            " l2\n"
            " l3\n"
        )
        self.assertEqual(unify(["l1", "l2", "l3"], ["n1", "n2", "l1", "l2", "l3"]), expected)

    def test_deletion_only_at_end(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,5 +1,3 @@\n"
            " l1\n"
            " l2\n"
            " l3\n"
            "-l4\n"
            "-l5\n"
        )
        self.assertEqual(
            unify(["l1", "l2", "l3", "l4", "l5"], ["l1", "l2", "l3"]), expected
        )

    def test_single_changed_character_of_line(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,2 +1,2 @@\n"
            " hello\n"
            "-world\n"
            "+world!\n"
        )
        self.assertEqual(unify(["hello", "world"], ["hello", "world!"]), expected)

    def test_two_separate_hunks(self):
        a = list("abcdefghijklmnop")
        b = list(a)
        b[3] = "C"  # d -> C
        b[-3] = "M"  # n -> M
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1,7 +1,7 @@\n"
            " a\n"
            " b\n"
            " c\n"
            "-d\n"
            "+C\n"
            " e\n"
            " f\n"
            " g\n"
            "@@ -11,6 +11,6 @@\n"
            " k\n"
            " l\n"
            " m\n"
            "-n\n"
            "+M\n"
            " o\n"
            " p\n"
        )
        self.assertEqual(unify(a, b), expected)

    def test_context_zero(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1 +1 @@\n"
            "-x\n"
            "+y\n"
        )
        self.assertEqual(unify(["x"], ["y"], context=0), expected)

    def test_context_zero_deletion_at_end(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -4,2 +3,0 @@\n"
            "-l4\n"
            "-l5\n"
        )
        self.assertEqual(
            unify(["l1", "l2", "l3", "l4", "l5"], ["l1", "l2", "l3"], context=0),
            expected,
        )

    def test_context_one_insertion_at_start(self):
        expected = (
            "--- old.txt\n"
            "+++ new.txt\n"
            "@@ -1 +1,3 @@\n"
            "+n1\n"
            "+n2\n"
            " l1\n"
        )
        self.assertEqual(
            unify(["l1", "l2", "l3"], ["n1", "n2", "l1", "l2", "l3"], context=1),
            expected,
        )

    def test_custom_file_names(self):
        out = unify(["a"], ["b"], fromfile="dir/old.py", tofile="dir/new.py")
        self.assertEqual(
            out.splitlines()[:2], ["--- dir/old.py", "+++ dir/new.py"]
        )

    def test_output_ends_with_single_newline(self):
        out = unify(["x"], ["y"])
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))

    def test_no_orphan_empty_hunks(self):
        # A change completely surrounded by content far away yields hunks
        # with both sides non-zero counts in the middle of the file.
        a = ["%d" % i for i in range(1, 51)]
        b = list(a)
        b[14] = "changed"
        out = unify(a, b)
        self.assertEqual(out.count("@@"), 2)  # header line only
        header = [ln for ln in out.splitlines() if ln.startswith("@@")][0]
        self.assertRegex(header, r"^@@ -\d+,\d+ \+\d+,\d+ @@$")


if __name__ == "__main__":
    unittest.main()