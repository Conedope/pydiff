"""Core Myers diff engine for pydiff.

This module implements the true Myers O(ND) shortest-edit-script
algorithm from scratch (no :mod:`difflib`), plus helpers that render the
resulting edit operations as a unified diff, as a colorized terminal
listing, and as file/directory aware comparisons.

The engine is line based: comparing two files means comparing their
lists of lines.
"""

from __future__ import annotations

import os
from typing import Iterable, List, NamedTuple, Optional, Sequence, Tuple

__all__ = [
    "Op",
    "myers_diff",
    "to_unified",
    "to_color",
    "read_lines",
    "diff_files",
    "diff_trees",
]

# ANSI SGR color codes (escapes are only emitted by to_color on request).
RED = "\x1b[31m"
GREEN = "\x1b[32m"
CYAN = "\x1b[36m"
RESET = "\x1b[0m"

_TAG_EQ = "eq"
_TAG_DEL = "del"
_TAG_INS = "ins"


class Op(NamedTuple):
    """A single edit operation.

    ``tag`` is one of ``'eq'``, ``'del'`` or ``'ins'``.  ``a_index`` and
    ``b_index`` are the 0-based line indices into the original (``a``)
    and modified (``b``) sequences; the index that does not apply to the
    tag is ``None``.
    """

    tag: str
    a_index: Optional[int] = None
    b_index: Optional[int] = None


def myers_diff(a: List[str], b: List[str]) -> List[Op]:
    """Compute the shortest edit script between ``a`` and ``b``.

    This is the linear-greedy ("furthest reaching") formulation of the
    Myers algorithm: it searches the edit graph diagonal by diagonal for
    increasing edit distance ``D`` until the end point ``(N, M)`` is
    reached, then backtracks through the stored ``V`` snapshots to
    recover the exact operation sequence.

    Tie-breaking prefers deletions before insertions (the standard
    convention, matching GNU diff's minus-before-plus output).
    """
    n, m = len(a), len(b)
    if n == 0 and m == 0:
        return []

    max_d = n + m
    offset = max_d + 1
    v = [0] * (2 * max_d + 3)
    v[1 + offset] = 0

    # Trace of the V array at the start of every distance iteration; this
    # is the D-table used for backtracking.
    trace: List[List[int]] = []
    final_d = 0
    found = False

    for d in range(max_d + 1):
        trace.append(v[:])
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and v[k - 1 + offset] < v[k + 1 + offset]):
                # From diagonal k+1 by an insertion (down move).
                x = v[k + 1 + offset]
            else:
                # From diagonal k-1 by a deletion (right move).  The
                # strict less-than above means ties pick this branch:
                # deletions are preferred over insertions.
                x = v[k - 1 + offset] + 1
            y = x - k
            while x < n and y < m and a[x] == b[y]:
                x += 1
                y += 1
            v[k + offset] = x
            if x >= n and y >= m:
                found = True
                final_d = d
                break
        if found:
            break

    # Backtrack through the trace, collecting operations in reverse.
    ops: List[Op] = []
    x, y = n, m
    for d in range(final_d, 0, -1):
        vd = trace[d]
        k = x - y
        if k == -d or (k != d and vd[k - 1 + offset] < vd[k + 1 + offset]):
            prev_k = k + 1
        else:
            prev_k = k - 1
        prev_x = vd[prev_k + offset]
        prev_y = prev_x - prev_k
        # Walk the snake back towards the previous edit point.
        while x > prev_x and y > prev_y:
            ops.append(Op(_TAG_EQ, x - 1, y - 1))
            x -= 1
            y -= 1
        if x == prev_x:
            ops.append(Op(_TAG_INS, None, y - 1))
        else:
            ops.append(Op(_TAG_DEL, x - 1, None))
        x, y = prev_x, prev_y

    # Remaining matches at the very start of the sequences.
    while x > 0 and y > 0:
        ops.append(Op(_TAG_EQ, x - 1, y - 1))
        x -= 1
        y -= 1

    ops.reverse()
    return ops


def _format_range(start: int, stop: int) -> str:
    """Render a 1-based line range for a hunk header.

    Mirrors GNU diff / difflib conventions: a single-line range drops the
    count, and an empty range begins at line 0 (``-0,0``)."""
    beginning = start + 1
    length = stop - start
    if length == 1:
        return str(beginning)
    if not length:
        beginning -= 1
    return "%d,%d" % (beginning, length)


def _opcodes_from_ops(ops: Iterable[Op]) -> List[Tuple[str, int, int, int, int]]:
    """Convert the flat operation stream into run-based opcodes.

    An opcode is ``(tag, i1, i2, j1, j2)`` with ``tag`` in
    ``equal``/``replace``/``delete``/``insert``.  Adjacent ``del`` and
    ``ins`` operations are folded into a single ``replace`` regardless
    of their internal order.
    """
    entries: List[Tuple[str, int, int, int, int]] = []
    ai = 0
    bi = 0
    for op in ops:
        if op.tag == _TAG_EQ:
            entries.append(("equal", ai, ai + 1, bi, bi + 1))
            ai += 1
            bi += 1
        elif op.tag == _TAG_DEL:
            entries.append(("delete", ai, ai + 1, bi, bi))
            ai += 1
        else:
            entries.append(("insert", ai, ai, bi, bi + 1))
            bi += 1

    # Coalesce consecutive equal entries.
    runs: List[Tuple[str, int, int, int, int]] = []
    for entry in entries:
        if runs and runs[-1][0] == "equal" and entry[0] == "equal":
            tag, i1, i2, j1, j2 = runs[-1]
            runs[-1] = (tag, i1, entry[2], j1, entry[4])
        else:
            runs.append(entry)

    # Fold consecutive delete/insert runs into a single change block.
    folded: List[Tuple[str, int, int, int, int]] = []
    current: Optional[Tuple[str, int, int, int, int]] = None
    for entry in runs:
        if entry[0] in ("delete", "insert"):
            if current is None:
                current = ("change", entry[1], entry[2], entry[3], entry[4])
            else:
                tag, i1, i2, j1, j2 = current
                current = (tag, i1, entry[2], j1, entry[4])
        else:
            if current is not None:
                folded.append(current)
                current = None
            folded.append(entry)
    if current is not None:
        folded.append(current)

    opcodes: List[Tuple[str, int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in folded:
        if tag == "change":
            if i1 < i2 and j1 < j2:
                opcodes.append(("replace", i1, i2, j1, j2))
            elif i1 < i2:
                opcodes.append(("delete", i1, i2, j1, j2))
            else:
                opcodes.append(("insert", i1, i2, j1, j2))
        else:
            opcodes.append((tag, i1, i2, j1, j2))
    return opcodes


def _grouped_opcodes(
    opcodes: Sequence[Tuple[str, int, int, int, int]], context: int
) -> List[List[Tuple[str, int, int, int, int]]]:
    """Split opcodes into hunk groups, padding each change with context."""
    n = max(context, 0)
    codes = [tuple(oc) for oc in opcodes]
    if not codes:
        return []
    if codes[0][0] == "equal":
        tag, i1, i2, j1, j2 = codes[0]
        codes[0] = (tag, max(i1, i2 - n), i2, max(j1, j2 - n), j2)
    if codes[-1][0] == "equal":
        tag, i1, i2, j1, j2 = codes[-1]
        codes[-1] = (tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n))
    nn = 2 * n
    groups: List[List[Tuple[str, int, int, int, int]]] = []
    group: List[Tuple[str, int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in codes:
        if tag == "equal" and i2 - i1 > nn:
            group.append((tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n)))
            groups.append(group)
            group = []
            i1, j1 = max(i1, i2 - n), max(j1, j2 - n)
        group.append((tag, i1, i2, j1, j2))
    if group and not (len(group) == 1 and group[0][0] == "equal"):
        groups.append(group)
    return groups


def _format_group(
    group: Sequence[Tuple[str, int, int, int, int]],
    a_lines: List[str],
    b_lines: List[str],
) -> List[str]:
    """Render one hunk group into header + prefixed body lines."""
    i1 = group[0][1]
    i2 = group[-1][2]
    j1 = group[0][3]
    j2 = group[-1][4]
    out = ["@@ -%s +%s @@" % (_format_range(i1, i2), _format_range(j1, j2))]
    for tag, gi1, gi2, gj1, gj2 in group:
        if tag == "equal":
            for k in range(gi1, gi2):
                out.append(" " + a_lines[k])
        elif tag in ("delete", "replace"):
            for k in range(gi1, gi2):
                out.append("-" + a_lines[k])
        if tag in ("insert", "replace"):
            for k in range(gj1, gj2):
                out.append("+" + b_lines[k])
    return out


def to_unified(
    a_lines: List[str],
    b_lines: List[str],
    ops: Sequence[Op],
    fromfile: str,
    tofile: str,
    context: int = 3,
) -> str:
    """Render a unified diff for ``ops`` between ``a_lines`` and ``b_lines``.

    The output starts with ``---``/``+++`` file headers, followed by one
    ``@@ -l,c +l,c @@`` hunk per group of changes.  Output ends with a
    single newline.  Returns ``""`` when the sequences are identical.
    """
    if not ops or all(op.tag == _TAG_EQ for op in ops):
        return ""
    groups = _grouped_opcodes(_opcodes_from_ops(ops), context)
    if not groups:
        return ""
    lines = ["--- %s" % fromfile, "+++ %s" % tofile]
    for group in groups:
        lines.extend(_format_group(group, a_lines, b_lines))
    return "\n".join(lines) + "\n"


def to_color(lines: Sequence[str], ops: Sequence[Op] = None) -> List[str]:
    """Colorize diff body lines for terminals.

    Lines are colored by their unified-diff prefix: context lines and
    the ``---``/``+++``/``Only in`` headers are left untouched, hunk
    headers turn cyan, deletions red and insertions green.  ``ops`` is
    accepted for interface compatibility with the diff pipeline; the
    color decision is made per line prefix.
    """
    del ops  # reserved for API compatibility
    out: List[str] = []
    for line in lines:
        if line.startswith("@@") and line.endswith("@@"):
            out.append(CYAN + line + RESET)
        elif line.startswith("-") and not line.startswith("---"):
            out.append(RED + line + RESET)
        elif line.startswith("+") and not line.startswith("+++"):
            out.append(GREEN + line + RESET)
        else:
            out.append(line)
    return out


def read_lines(
    path: str, ignore_case: bool = False, strip_trailing_cr: bool = False
) -> List[str]:
    """Read ``path`` and split it into lines.

    A trailing newline does not produce an extra empty line.  With
    ``strip_trailing_cr`` a trailing carriage return is removed from
    every line; with ``ignore_case`` every line is case-folded.
    """
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    if text == "":
        lines: List[str] = []
    elif text.endswith("\n"):
        lines = text[:-1].split("\n")
    else:
        lines = text.split("\n")
    if strip_trailing_cr:
        lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    if ignore_case:
        lines = [line.casefold() for line in lines]
    return lines


def diff_files(
    path_a: str,
    path_b: str,
    context: int = 3,
    ignore_case: bool = False,
    strip_trailing_cr: bool = False,
) -> str:
    """Return the unified diff between two files, or ``""`` if equal."""
    a_lines = read_lines(path_a, ignore_case=ignore_case, strip_trailing_cr=strip_trailing_cr)
    b_lines = read_lines(path_b, ignore_case=ignore_case, strip_trailing_cr=strip_trailing_cr)
    ops = myers_diff(a_lines, b_lines)
    if all(op.tag == _TAG_EQ for op in ops):
        return ""
    return to_unified(
        a_lines, b_lines, ops, os.fspath(path_a), os.fspath(path_b), context
    )


def _collect_files(top: str) -> set:
    """Return the set of relative file paths found under ``top``."""
    found = set()
    for root, dirs, files in os.walk(top):
        dirs.sort()
        for name in files:
            found.add(os.path.relpath(os.path.join(root, name), top))
    return found


def _only_in(dirpath: str, rel: str) -> str:
    """Render a GNU-style ``Only in <dir>: <name>`` line, retaining the
    directory component for entries nested in subdirectories."""
    parent, base = os.path.split(rel)
    if parent:
        where = os.path.join(dirpath, parent)
    else:
        where = dirpath
    return "Only in %s: %s" % (where, base)


def diff_trees(
    dir_a: str,
    dir_b: str,
    context: int = 3,
    ignore_case: bool = False,
    strip_trailing_cr: bool = False,
) -> str:
    """Recursively compare two directories.

    Common files are diffed pairwise, files present in only one tree are
    reported with ``Only in ...`` lines.  Returns ``""`` when the trees
    are identical.
    """
    files_a = _collect_files(dir_a)
    files_b = _collect_files(dir_b)
    parts: List[str] = []

    for rel in sorted(files_a & files_b):
        text = diff_files(
            os.path.join(dir_a, rel),
            os.path.join(dir_b, rel),
            context,
            ignore_case=ignore_case,
            strip_trailing_cr=strip_trailing_cr,
        )
        if text:
            parts.append(text)

    for rel in sorted(files_a - files_b):
        parts.append(_only_in(dir_a, rel))
    for rel in sorted(files_b - files_a):
        parts.append(_only_in(dir_b, rel))

    if not parts:
        return ""
    return "\n".join(parts)