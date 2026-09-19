import unittest

from pydiff.diff import CYAN, GREEN, RED, RESET, to_color


class ToColorTest(unittest.TestCase):
    def test_context_lines_untouched(self):
        self.assertEqual(to_color([" hello", " world"]), [" hello", " world"])

    def test_deletion_lines_red(self):
        self.assertEqual(to_color(["-old", "-gone"]), [RED + "-old" + RESET, RED + "-gone" + RESET])

    def test_insertion_lines_green(self):
        self.assertEqual(to_color(["+new", "+added"]), [GREEN + "+new" + RESET, GREEN + "+added" + RESET])

    def test_hunk_header_cyan(self):
        self.assertEqual(to_color(["@@ -1,2 +1,2 @@"]), [CYAN + "@@ -1,2 +1,2 @@" + RESET])

    def test_file_headers_left_plain(self):
        lines = ["--- old.txt", "+++ new.txt"]
        self.assertEqual(to_color(lines), lines)

    def test_only_in_lines_left_plain(self):
        lines = ["Only in dir: extra.txt"]
        self.assertEqual(to_color(lines), lines)

    def test_no_escapes_without_coloring(self):
        out = to_color([" a", "-a", "+b", " c"])
        self.assertIn(RED, out[1])
        self.assertIn(GREEN, out[2])
        self.assertNotIn("\x1b", out[0])
        self.assertNotIn("\x1b", out[3])

    def test_accepts_ops_parameter(self):
        from pydiff.diff import myers_diff

        ops = myers_diff(["a"], ["b"])
        out = to_color(["-a", "+b"], ops)
        self.assertEqual(out[0], RED + "-a" + RESET)
        self.assertEqual(out[1], GREEN + "+b" + RESET)

    def test_two_hunk_full_diff_coloring(self):
        diff = [
            "--- old.txt",
            "+++ new.txt",
            "@@ -1,3 +1,3 @@",
            " one",
            "-two",
            "+TWO",
            " three",
        ]
        out = to_color(diff)
        self.assertEqual(out[0], "--- old.txt")
        self.assertEqual(out[1], "+++ new.txt")
        self.assertEqual(out[2], CYAN + "@@ -1,3 +1,3 @@" + RESET)
        self.assertEqual(out[3], " one")
        self.assertEqual(out[4], RED + "-two" + RESET)
        self.assertEqual(out[5], GREEN + "+TWO" + RESET)
        self.assertEqual(out[6], " three")


if __name__ == "__main__":
    unittest.main()