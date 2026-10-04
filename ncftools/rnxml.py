#!/usr/bin/env python3
"""
rnxml - Rename dimr.xml to dimr_config.xml

D-HYDRO / Delft3D FM writes its DIMR control file as dimr.xml, while the DIMR
runner expects dimr_config.xml. This tool renames the file in place.

The file contents are not touched. If the target name already exists the
rename is refused unless --force is given, in which case a .bak copy of the
existing target is kept (unless --no-backup).
"""

import argparse
import importlib.metadata
import os
import shutil
import sys
from pathlib import Path

DEFAULT_INPUT = 'dimr.xml'
DEFAULT_OUTPUT_NAME = 'dimr_config.xml'


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def rename_xml(
    input_file=DEFAULT_INPUT,
    output_name=DEFAULT_OUTPUT_NAME,
    force=False,
    backup=True,
    quiet=False,
):
    """
    Rename an XML file, keeping it in the same directory.

    Args:
        input_file (str): Path to the file to rename (default: dimr.xml).
        output_name (str): New file name, without a directory part
            (default: dimr_config.xml).
        force (bool): Overwrite the target if it already exists.
        backup (bool): When overwriting, keep a .bak copy of the old target.
        quiet (bool): Suppress non-error output.

    Returns:
        Path: Path of the renamed file.

    Raises:
        FileNotFoundError: The input file does not exist.
        ValueError: output_name contains a directory part.
        FileExistsError: The target exists and force is False.
    """
    src = Path(input_file)
    if not src.is_file():
        raise FileNotFoundError(f"file not found: {src}")

    if os.path.dirname(output_name):
        raise ValueError(
            f"--output-name must be a file name, not a path: {output_name}"
        )

    dst = src.parent / output_name

    if src.resolve() == dst.resolve():
        _print(f"{src} is already named {output_name} - nothing to do.", quiet)
        return dst

    if dst.exists():
        if not force:
            raise FileExistsError(
                f"{dst} already exists - use --force to overwrite it"
            )
        if backup:
            bak = dst.with_suffix(dst.suffix + '.bak')
            shutil.copy2(dst, bak)
            _print(f"Backup written: {bak}", quiet)

    os.replace(src, dst)
    _print(f"Renamed: {src} -> {dst}", quiet)
    return dst


def main():
    parser = argparse.ArgumentParser(
        prog='rnxml',
        description='Rename dimr.xml to dimr_config.xml',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rnxml
  rnxml dimr.xml
  rnxml -i dimr.xml             # same, with the -i flag
  rnxml model/dimr.xml
  rnxml dimr.xml -o dimr_config.xml --force
  rnxml dimr.xml -q
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {importlib.metadata.version("ncftools")}',
    )
    parser.add_argument(
        'file',
        nargs='?',
        metavar='FILE',
        help=f'File to rename (default: {DEFAULT_INPUT})',
    )
    parser.add_argument(
        '-i', '--input',
        metavar='FILE',
        help='Same as FILE (kept for backward compatibility)',
    )
    parser.add_argument(
        '-o', '--output-name',
        default=DEFAULT_OUTPUT_NAME,
        metavar='NAME',
        help=f'New file name, kept in the same folder (default: {DEFAULT_OUTPUT_NAME})',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite the target file if it already exists',
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not keep a .bak copy of an overwritten target',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output',
    )

    args = parser.parse_args()

    if args.file and args.input:
        parser.error('give the file either as FILE or with -i, not both')
    args.input = args.file or args.input or DEFAULT_INPUT

    try:
        dst = rename_xml(
            args.input,
            output_name=args.output_name,
            force=args.force,
            backup=not args.no_backup,
            quiet=args.quiet,
        )
        if args.quiet:
            print(dst)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
