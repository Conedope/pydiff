# pydiff

`pydiff` is a small, dependency-free command line tool that produces
**unified diffs** between two text files — or two directories of text files.
Its diffing core is a **Myers O(ND) shortest-edit-script algorithm implemented
from scratch** (no `difflib`), and it ships with a human color mode for
terminals. It uses only the Python standard library.

## Features

- True **Myers O(ND)** diff engine with backtracking and deletion-first
  tie-breaking (GNU-style minus-before-plus output).
- Standard **unified diff** output (`---` / `+++` headers, `@@ -l,c +l,c @@`
  hunks, correct `0` counts such as `-0,0 +1`), byte-identical to
  `diff -u` apart from the intentionally omitted file timestamps.
- **Recursive directory comparison** (`-r`) with `Only in ...` lines for
  files present in just one tree.
- Human **color mode** (red deletions / green insertions / cyan hunks) that
  auto-enables on a TTY, or can be forced with `--color always`.
- `--ignore-case`, `--strip-trailing-cr`, adjustable context
  (`-c/--lines`).
- Standard exit codes: `0` identical, `1` files differ, `2` error.

## Install

```console
$ pip install .
$ pydiff --version
pydiff 1.0.0
```

Or run it out of the box without installing anything:

```console
$ python3 -m pydiff old.txt new.txt
```

## Usage

Compare two files:

```console
$ pydiff old.txt new.txt
```

The output above is the following **real** `pydiff` run (verified against
`diff -u`, whose hunk bodies are byte-identical):

```diff
--- old.txt
+++ new.txt
@@ -1,8 +1,9 @@
 alpha
-beta
+BETA
 gamma
 delta
-epsilon
+Epsilon
 zeta
 eta
 theta
+omega
```

Recursively compare two directories:

```console
$ pydiff -r ta tb
--- ta/sub/nested.txt
+++ tb/sub/nested.txt
@@ -1,2 +1,2 @@
 a
-b
+B

Only in ta: only-a.txt
Only in tb: only-b.txt
```

Colorized output (shown with escapes visible via `cat -v`):

```console
$ pydiff --color always old.txt new.txt | cat -v
--- old.txt
+++ new.txt
^[[36m@@ -1,8 +1,9 @@^[[0m
 alpha
^[[31m-beta^[[0m
^[[32m+BETA^[[0m
```

Exit codes (handy for scripts):

```console
$ pydiff old.txt old.txt; echo $?        # identical  -> 0
0
$ pydiff old.txt new.txt >/dev/null; echo $?   # differs   -> 1
1
$ pydiff missing.txt other.txt; echo $?  # error     -> 2
pydiff: error: [Errno 2] No such file or directory: 'missing.txt'
2
```

## Reference

| Flag | Description |
| --- | --- |
| `OLD NEW` | the two files (or, with `-r`, directories) to compare |
| `-u`, `--unified` | unified output (the default) |
| `-c CONTEXT`, `--lines CONTEXT` | context lines around each change (default `3`) |
| `-r`, `--recursive` | recursively compare two directories |
| `--color WHEN` | `never`, `auto` (default; only on a terminal) or `always`; a bare `--color` means `--color always` |
| `--no-color` | shorthand for `--color never` |
| `--strip-trailing-cr` | strip a trailing carriage return from each line before comparing |
| `--ignore-case` | ignore case when comparing lines (output shows the normalized comparison) |
| `--version` | print the version and exit |
| `--help` | show usage and exit |

Exit codes: `0` identical, `1` differs, `2` error (missing files,
directory-without-`-r`, etc.).

## The algorithm

`pydiff/diff.py` implements the classic **Myers "furthest reaching"
O(ND) algorithm** (E. Myers, *An O(ND) Difference Algorithm and Its
Variations*, 1986):

1. The problem is framed as a shortest-path search on an edit graph:
   diagonals advance freely over matching lines, horizontal moves delete
   one line and vertical moves insert one line.
2. The search grows a diagonal `V`-frontier for increasing edit distance
   `D` until the bottom-right corner `(N, M)` is reached — D is the exact
   minimal edit distance.
3. A full trace of the `V`-arrays is kept along the way (the D-table) and
   walk **backwards** through it to recover the exact sequence of
   `eq` / `del` / `ins` operations.

Tie-breaking prefers **deletions before insertions**, matching the standard
GNU `diff` ordering. The only inputs are the two line sequences — no third
party code, no `difflib`.

The test suite validates the engine against an independent dynamic-program
LCS oracle over thousands of small sequences (the ops replay exactly to the
inputs and always have the provably minimal edit distance), plus golden
unified-diff and CLI exit-code checks.

## Development

Run the tests (Python ≥ 3.9):

```console
$ python3 -m unittest discover -s tests -v
75 tests, all pass
```

The suite covers: Myers correctness (replay + minimality + tie-breaking,
including an exhaustive scan of all small sequences), hand-checked unified
diff golden strings, color output, `--ignore-case` / `--strip-trailing-cr`,
recursive tree comparison, and CLI exit-code behaviour via subprocesses.

## License

MIT — © 2026 Conedope. See [LICENSE](LICENSE).