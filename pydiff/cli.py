"""Command line interface for pydiff."""

import argparse
import os
import sys

from pydiff import __version__
from pydiff.diff import diff_files, diff_trees, to_color

__all__ = ["main"]

_DESCRIPTION = (
    "pydiff: unified diffs between two text files or two directories of text "
    "files, powered by a from-scratch Myers O(ND) diff engine (stdlib only)."
)

_COLOR_CHOICES = ("never", "auto", "always")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pydiff",
        description=_DESCRIPTION,
        epilog=("Exit codes: 0 identical, 1 files differ, 2 error."),
    )
    parser.add_argument("old", metavar="OLD", help="original file or directory")
    parser.add_argument("new", metavar="NEW", help="modified file or directory")
    parser.add_argument(
        "-u",
        "--unified",
        action="store_true",
        help="output unified diff (this is the default)",
    )
    parser.add_argument(
        "-c",
        "--lines",
        type=int,
        default=3,
        metavar="CONTEXT",
        help="number of context lines around changes (default: %(default)s)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="recursively compare two directories",
    )
    parser.add_argument(
        "--color",
        choices=_COLOR_CHOICES,
        default="auto",
        metavar="WHEN",
        help=(
            "when to colorize output: %(choices)s (default: %(default)s, "
            "i.e. only on a terminal); bare --color means --color always"
        ),
    )
    parser.add_argument(
        "--no-color", action="store_true", help="shorthand for --color never"
    )
    parser.add_argument(
        "--strip-trailing-cr",
        action="store_true",
        help="strip a trailing carriage return from every line before comparing",
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="ignore case when comparing lines",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + __version__,
    )
    return parser


def _expand_color(argv):
    """Allow a bare ``--color`` to mean ``--color always``.

    argparse-style ``nargs='?', const=...`` options happily swallow the
    next positional argument, so we normalize before parsing.
    """
    argv = list(argv)
    out = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--color":
            nxt = argv[i + 1] if i + 1 < len(argv) else None
            if nxt in _COLOR_CHOICES:
                out.extend([token, nxt])
                i += 2
                continue
            out.extend(["--color", "always"])
        else:
            out.append(token)
        i += 1
    return out


def main(argv=None) -> int:
    """CLI entry point.  Returns 0 (identical), 1 (differ) or 2 (error)."""
    parser = _build_parser()
    argv = _expand_color(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)

    color = "never" if args.no_color else args.color

    try:
        if os.path.isdir(args.old) and os.path.isdir(args.new):
            if not args.recursive:
                print(
                    "pydiff: error: %r and %r are directories "
                    "(use -r to compare them recursively)"
                    % (args.old, args.new),
                    file=sys.stderr,
                )
                return 2
            text = diff_trees(
                args.old,
                args.new,
                args.lines,
                ignore_case=args.ignore_case,
                strip_trailing_cr=args.strip_trailing_cr,
            )
        elif os.path.isdir(args.old) or os.path.isdir(args.new):
            print(
                "pydiff: error: cannot compare a file with a directory",
                file=sys.stderr,
            )
            return 2
        else:
            text = diff_files(
                args.old,
                args.new,
                args.lines,
                ignore_case=args.ignore_case,
                strip_trailing_cr=args.strip_trailing_cr,
            )
    except OSError as exc:
        print("pydiff: error: %s" % exc, file=sys.stderr)
        return 2

    want_color = color == "always" or (
        color == "auto"
        and "NO_COLOR" not in os.environ
        and sys.stdout.isatty()
    )
    if text and want_color:
        text = "\n".join(to_color(text.splitlines())) + "\n"

    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")

    return 1 if text else 0


if __name__ == "__main__":
    sys.exit(main())