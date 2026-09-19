import unittest

from pydiff.diff import Op, myers_diff


def edit_distance(a, b):
    """Independent oracle: LCS-based edit distance (insert/delete cost 1).

    Minimal edit scripts built only from insertions and deletions cost
    ``len(a) + len(b) - 2 * len(LCS(a, b))``.  Computed here with a plain
    dynamic program, independent of the implementation under test (and of
    difflib).
    """
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return len(a) + len(b) - 2 * dp[len(a)][len(b)]


def sequences(alphabet, max_len):
    """Yield every sequence over ``alphabet`` of length 0..max_len."""
    current = [[]]
    yield []
    for _ in range(max_len):
        nxt = []
        for seq in current:
            for ch in alphabet:
                s = list(seq) + [ch]
                nxt.append(s)
                yield s
        current = nxt


class MyersDiffTest(unittest.TestCase):
    def assert_replays(self, a, b, ops):
        """Strong property: replaying the ops reconstructs both inputs."""
        ai = bi = 0
        for op in ops:
            if op.tag == "eq":
                self.assertIsNotNone(op.a_index)
                self.assertIsNotNone(op.b_index)
                self.assertEqual(a[op.a_index], b[op.b_index])
                self.assertEqual(op.a_index, ai)
                self.assertEqual(op.b_index, bi)
                ai += 1
                bi += 1
            elif op.tag == "del":
                self.assertIsNone(op.b_index)
                self.assertEqual(op.a_index, ai)
                ai += 1
            elif op.tag == "ins":
                self.assertIsNone(op.a_index)
                self.assertEqual(op.b_index, bi)
                bi += 1
            else:
                self.fail("unknown op tag %r" % (op.tag,))
        self.assertEqual(ai, len(a))
        self.assertEqual(bi, len(b))

    def assert_minimal(self, a, b, ops):
        n_changed = sum(1 for op in ops if op.tag != "eq")
        self.assertEqual(n_changed, edit_distance(a, b))

    # ---- hand-computed exact scripts ----

    def test_identical(self):
        self.assertEqual(
            myers_diff(["a", "b"], ["a", "b"]),
            [Op("eq", 0, 0), Op("eq", 1, 1)],
        )

    def test_empty_inputs(self):
        self.assertEqual(myers_diff([], []), [])
        self.assertEqual(
            myers_diff([], ["x", "y"]),
            [Op("ins", None, 0), Op("ins", None, 1)],
        )
        self.assertEqual(
            myers_diff(["x", "y"], []),
            [Op("del", 0, None), Op("del", 1, None)],
        )

    def test_single_char_replacement_prefers_deletion_first(self):
        # "x" -> "y": no shared content, so the script is one deletion
        # followed by one insertion (tie-breaking convention).
        self.assertEqual(
            myers_diff(["x"], ["y"]),
            [Op("del", 0, None), Op("ins", None, 0)],
        )

    def test_middle_change_exact_ops(self):
        self.assertEqual(
            myers_diff(["a", "b", "c"], ["a", "x", "c"]),
            [Op("eq", 0, 0), Op("del", 1, None), Op("ins", None, 1), Op("eq", 2, 2)],
        )

    def test_edit_scripts_on_small_fixtures(self):
        cases = [
            (["a", "b", "c", "d"], ["a", "c", "d", "e"],
             [Op("eq", 0, 0), Op("del", 1, None), Op("eq", 2, 1),
              Op("eq", 3, 2), Op("ins", None, 3)]),
            (["a", "b", "c", "d"], ["a", "x", "c", "d"],
             [Op("eq", 0, 0), Op("del", 1, None), Op("ins", None, 1),
              Op("eq", 2, 2), Op("eq", 3, 3)]),
            (["a", "b"], ["a", "y", "z"],
             [Op("eq", 0, 0), Op("del", 1, None), Op("ins", None, 1),
              Op("ins", None, 2)]),
            (["a", "b", "c"], ["b", "c"],
             [Op("del", 0, None), Op("eq", 1, 0), Op("eq", 2, 1)]),
            (["a", "b", "c"], ["a", "b", "c", "d", "e"],
             [Op("eq", 0, 0), Op("eq", 1, 1), Op("eq", 2, 2),
              Op("ins", None, 3), Op("ins", None, 4)]),
            (list("kitten"), list("sitting"),
             [Op("del", 0, None), Op("ins", None, 0),
              Op("eq", 1, 1), Op("eq", 2, 2), Op("eq", 3, 3),
              Op("del", 4, None), Op("ins", None, 4),
              Op("eq", 5, 5), Op("ins", None, 6)]),
            (["alpha", "beta"], ["gamma", "delta"],
             [Op("del", 0, None), Op("del", 1, None),
              Op("ins", None, 0), Op("ins", None, 1)]),
        ]
        for a, b, expected in cases:
            self.assertEqual(myers_diff(a, b), expected, (a, b))

    # ---- hand-computed minimal edit distances ----

    def test_hand_computed_distances(self):
        cases = [
            ("abc", "abc", 0),
            ("abc", "axc", 2),
            ("", "xyz", 3),
            ("xyz", "", 3),
            ("kitten", "sitting", 5),
            ("abcd", "acde", 2),
            ("aba", "baa", 2),
        ]
        for left, right, expected in cases:
            a = list(left)
            b = list(right)
            ops = myers_diff(a, b)
            self.assert_replays(a, b, ops)
            n_changed = sum(1 for op in ops if op.tag != "eq")
            self.assertEqual(n_changed, expected, (left, right, ops))

    def test_fixture_distances_multiline(self):
        cases = [
            (["kitten", "sat"], ["kitten", "sat"], 0),
            (["kitten", "sat"], ["kitten", "sat", "down"], 1),
            (["a", "b", "c"], ["a", "b", "c", "d"], 1),
            (["a", "b", "c", "e"], ["a", "b", "c", "d", "e"], 1),
            (["x", "y", "z"], ["a", "y", "z"], 2),
            (["alpha", "beta"], ["gamma", "delta"], 4),
        ]
        for a, b, expected in cases:
            ops = myers_diff(a, b)
            self.assert_replays(a, b, ops)
            n_changed = sum(1 for op in ops if op.tag != "eq")
            self.assertEqual(n_changed, expected, (a, b, ops))

    # ---- heavy property checks ----

    def test_exhaustive_small_sequences(self):
        alphabet = ["a", "b"]
        corpus = list(sequences(alphabet, 4))
        for a in corpus:
            for b in corpus:
                ops = myers_diff(a, b)
                self.assert_replays(a, b, ops)
                self.assert_minimal(a, b, ops)

    def test_exhaustive_small_sequences_three_symbols(self):
        alphabet = ["a", "b", "c"]
        corpus = list(sequences(alphabet, 3))
        for a in corpus:
            for b in corpus:
                ops = myers_diff(a, b)
                self.assert_replays(a, b, ops)
                self.assert_minimal(a, b, ops)

    def test_exhaustive_empty_companions(self):
        alphabet = ["x", "y"]
        corpus = list(sequences(alphabet, 5))
        for a in corpus:
            for b in ([], ["y"] * len(a)):
                ops = myers_diff(a, b)
                self.assert_replays(a, b, ops)
                self.assert_minimal(a, b, ops)

    def test_del_before_ins_tie_breaking_again(self):
        # a swap with no other anchor: deletions are emitted before
        # insertions at each changed position.
        ops = myers_diff(list("swap"), list("swip"))
        tags = [op.tag for op in ops]
        self.assertEqual(tags, ["eq", "eq", "del", "ins", "eq"])


if __name__ == "__main__":
    unittest.main()