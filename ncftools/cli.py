#!/usr/bin/env python
"""
Top-level `ncftools` command. Running `ncftools -h` (or with no arguments)
prints the same information shown by `ncftools-info`.
"""

import sys

from . import describe


def _print_info(tool=None):
    argv_backup = sys.argv
    try:
        sys.argv = ['ncftools-info'] + ([tool] if tool else [])
        describe.main()
    finally:
        sys.argv = argv_backup


def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        _print_info()
        return

    tool = args[0]
    if tool in describe.TOOL_DESCRIPTIONS:
        _print_info(tool)
        return

    print(f"Unknown option or tool: {tool}", file=sys.stderr)
    print("Run 'ncftools -h' to see available tools.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
