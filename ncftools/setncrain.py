#!/usr/bin/env python3
"""
setncrain - Point a D-Flow FM model at a NetCDF rainfall forcing file

In every [Meteo] block of the .ext file:
    quantity        -> rainfall
    forcingFile     -> <user specified *.nc>
    forcingFileType -> netcdf

If the .ext file does not exist it is created from the hard-coded TEMPLATE
below, already pointing at the given NetCDF file, and ExtForceFileNew in the
model definition file (*.mdu) is set to it.

The NetCDF time axis is read and the model times in the .mdu are adjusted to it:
    RefDate -> the date of the first time stamp (midnight)
    TStart  -> offset of the first time stamp from RefDate (in Tunit)
    TStop   -> offset of the last  time stamp from RefDate (in Tunit)
"""

import argparse
import importlib.metadata
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

REPLACEMENTS = {
    "quantity": "rainfall",
    "forcingfiletype": "netcdf",
    # forcingFile is filled in at runtime
}

# Hard-coded .ext contents, used when the .ext file is missing.
# Edit here to change the generated file; {forcing_file} is substituted.
TEMPLATE = """[General]
fileVersion=2.02
fileType=extForce

[Meteo]
quantity=rainfall
forcingFile={forcing_file}
forcingFileType=netcdf
interpolationMethod=linearSpaceTime
operand=O

"""

CF_UNITS = {
    "second": 1.0, "seconds": 1.0, "sec": 1.0, "secs": 1.0, "s": 1.0,
    "minute": 60.0, "minutes": 60.0, "min": 60.0, "mins": 60.0,
    "hour": 3600.0, "hours": 3600.0, "hr": 3600.0, "hrs": 3600.0, "h": 3600.0,
    "day": 86400.0, "days": 86400.0, "d": 86400.0,
}
# TStart/TStop are expressed in the model's Tunit
TUNIT_SECONDS = {"S": 1.0, "M": 60.0, "H": 3600.0, "D": 86400.0}


def _print(msg, quiet=False):
    if not quiet:
        print(msg)


def create(ext_path, nc_file, quiet=False):
    """
    Create a new .ext file from the hard-coded TEMPLATE, pointing at nc_file.

    Args:
        ext_path (Path): Path of the .ext file to write.
        nc_file (str): forcingFile value to write into the [Meteo] block.
        quiet (bool): Suppress non-error output.
    """
    ext_path = Path(ext_path)
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    # D-Flow FM input files conventionally use CRLF
    with ext_path.open("w", newline="\r\n") as f:
        f.write(TEMPLATE.format(forcing_file=nc_file))
    _print(f"Created: {ext_path}", quiet)
    _print(
        f"  quantity=rainfall, forcingFile={nc_file}, forcingFileType=netcdf",
        quiet,
    )


def find_mdu(ext_path) -> Optional[Path]:
    """Locate the .mdu next to the .ext file (FM_model.mdu wins if several)."""
    ext_path = Path(ext_path)
    folder = ext_path.parent if str(ext_path.parent) else Path(".")
    mdus = sorted(folder.glob("*.mdu"))
    if not mdus:
        return None
    for m in mdus:
        if m.stem.lower() == "fm_model":
            return m
    return mdus[0]


def read_mdu_value(mdu_path, key) -> Optional[str]:
    """Return the value of a single .mdu key, or None if it is absent."""
    with Path(mdu_path).open("r", newline="") as f:
        for line in f:
            name, sep, rest = line.partition("=")
            if sep and name.strip().lower() == key.lower():
                return rest.partition("#")[0].strip()
    return None


def update_mdu(mdu_path, settings, backup=True, quiet=False):
    """
    Set the given key=value pairs in the .mdu, preserving layout and comments.

    Args:
        mdu_path (Path): Path to the model definition file.
        settings (dict): Key/value pairs to apply.
        backup (bool): Write a .bak copy before overwriting.
        quiet (bool): Suppress non-error output.

    Returns:
        list[str]: Human-readable description of each change made.
    """
    mdu_path = Path(mdu_path)
    wanted = {k.lower(): (k, str(v)) for k, v in settings.items()}

    with mdu_path.open("r", newline="") as f:
        lines = f.read().splitlines(keepends=True)

    out, changed, seen = [], [], set()
    for line in lines:
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        key, sep, rest = body.partition("=")
        name = key.strip().lower()

        if sep and name in wanted:
            seen.add(name)
            label, value = wanted[name]
            val_part, hash_sep, comment = rest.partition("#")
            old = val_part.strip()
            if old != value:
                # keep the original column of the trailing comment
                lead = val_part[: len(val_part) - len(val_part.lstrip())] if old else " "
                new_val = (lead + value).ljust(len(val_part))
                if hash_sep and not new_val.endswith(" "):
                    new_val += " "
                line = f"{key}={new_val}{hash_sep}{comment}" + eol
                changed.append(f"{label} = {old or '<empty>'} -> {value}")

        out.append(line)

    for name, (label, value) in wanted.items():
        if name not in seen:
            print(
                f"! {label} not found in {mdu_path} - set it to {value} manually.",
                file=sys.stderr,
            )

    if not changed:
        _print(f"{mdu_path}: already up to date.", quiet)
        return changed

    if backup:
        bak = mdu_path.with_suffix(mdu_path.suffix + ".bak")
        shutil.copy2(mdu_path, bak)
        _print(f"Backup written: {bak}", quiet)

    with mdu_path.open("w", newline="") as f:
        f.write("".join(out))
    _print(f"Updated: {mdu_path}", quiet)
    for c in changed:
        _print(f"  {c}", quiet)
    return changed


def rewrite(ext_path, nc_file, backup=True, quiet=False):
    """
    Rewrite the [Meteo] blocks of an existing .ext file for NetCDF rainfall.

    Args:
        ext_path (Path): Path to the existing .ext file.
        nc_file (str): forcingFile value to write.
        backup (bool): Write a .bak copy before overwriting.
        quiet (bool): Suppress non-error output.

    Returns:
        list[str]: Human-readable description of each change made.
    """
    ext_path = Path(ext_path)
    if not ext_path.is_file():
        raise FileNotFoundError(f"ext file not found: {ext_path}")

    # newline='' keeps original CRLF/LF line endings intact
    with ext_path.open("r", newline="") as f:
        raw = f.read()

    lines = raw.splitlines(keepends=True)
    out = []
    in_meteo = False
    changed = []

    for line in lines:
        stripped = line.strip()
        body, eol = line.rstrip("\r\n"), line[len(line.rstrip("\r\n")):]

        if stripped.startswith("["):
            in_meteo = stripped.lower() == "[meteo]"
            out.append(line)
            continue

        if in_meteo and "=" in body:
            key, _, old = body.partition("=")
            # split off any inline comment so it is preserved
            old_val, sep, comment = old.partition("#")
            name = key.strip().lower()

            new_val = None
            if name == "forcingfile":
                new_val = nc_file
            elif name in REPLACEMENTS:
                new_val = REPLACEMENTS[name]

            if new_val is not None:
                # keep original spacing style around '=' and the column of any
                # trailing comment
                lead = old_val[: len(old_val) - len(old_val.lstrip())]
                padded = lead + new_val
                if sep:  # an inline comment follows: keep its column
                    padded = padded.ljust(len(old_val))
                    if not padded.endswith(" "):
                        padded += " "
                body = f"{key}={padded}{sep}{comment}"
                changed.append(f"{key.strip()} = {old_val.strip()} -> {new_val}")
                line = body + eol

        out.append(line)

    if not changed:
        _print("No [Meteo] keys matched - file left unchanged.", quiet)
        return changed

    if backup:
        bak = ext_path.with_suffix(ext_path.suffix + ".bak")
        shutil.copy2(ext_path, bak)
        _print(f"Backup written: {bak}", quiet)

    with ext_path.open("w", newline="") as f:
        f.write("".join(out))

    _print(f"Updated: {ext_path}", quiet)
    for c in changed:
        _print(f"  {c}", quiet)
    return changed


def _open_time_var(nc_path):
    """Return (values, units_string) of the time coordinate of a NetCDF file."""

    def pick(names, get_attr):
        for cand in ("time", "TIME", "Time", "t"):
            if cand in names:
                return cand
        for n in names:  # fall back to any CF time-like variable
            units = (get_attr(n, "units") or "").lower()
            if " since " in units or (get_attr(n, "axis") or "") == "T":
                return n
        return None

    try:
        import netCDF4  # the usual reader in a Delft3D FM python environment
    except ImportError:
        pass
    else:
        with netCDF4.Dataset(str(nc_path)) as ds:
            def get(n, a):
                return getattr(ds.variables[n], a, None)

            name = pick(list(ds.variables), get)
            if name is None:
                raise ValueError(f"no time variable found in {nc_path}")
            v = ds.variables[name]
            return [float(x) for x in v[:].ravel()], str(getattr(v, "units", ""))

    try:
        import xarray as xr  # second choice
    except ImportError:
        pass
    else:
        with xr.open_dataset(str(nc_path), decode_times=False) as ds:
            def get(n, a):
                return ds[n].attrs.get(a)

            name = pick(list(ds.variables), get)
            if name is None:
                raise ValueError(f"no time variable found in {nc_path}")
            v = ds[name]
            return [float(x) for x in v.values.ravel()], str(v.attrs.get("units", ""))

    try:
        from scipy.io import netcdf_file  # last resort, NetCDF3 only
    except ImportError as exc:
        raise ImportError(
            "reading the NetCDF file needs one of netCDF4, xarray or scipy - "
            "install with:  pip install netCDF4"
        ) from exc

    with netcdf_file(str(nc_path), "r", mmap=False) as ds:
        def get(n, a):
            val = getattr(ds.variables[n], a, None)
            return val.decode() if isinstance(val, bytes) else val

        name = pick(list(ds.variables), get)
        if name is None:
            raise ValueError(f"no time variable found in {nc_path}")
        v = ds.variables[name]
        units = getattr(v, "units", b"")
        return (
            [float(x) for x in v[:].ravel()],
            units.decode() if isinstance(units, bytes) else str(units),
        )


def parse_cf_units(units):
    """'minutes since 1970-01-01 00:00:00.0 +0000' -> (scale in s, epoch)."""
    unit, _, epoch_txt = units.partition(" since ")
    scale = CF_UNITS.get(unit.strip().lower())
    if scale is None:
        raise ValueError(f"unsupported time unit in '{units}'")

    txt = epoch_txt.strip()
    # drop the time zone, then normalise an ISO 'T' separator to a space
    txt = re.sub(r"\s*(Z|UTC|GMT)\s*$", "", txt)          # ... 00:00:00 UTC
    txt = re.sub(r"\s+[+-]\d{2}:?\d{2}\s*$", "", txt)     # ... 00:00:00 +0000
    txt = re.sub(r"(?<=\d)T(?=\d)", " ", txt).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return scale, datetime.strptime(txt, fmt)
        except ValueError:
            continue
    raise ValueError(f"cannot parse the reference date in '{units}'")


def nc_time_range(nc_path):
    """First and last time stamp in the NetCDF file, as datetimes."""
    values, units = _open_time_var(nc_path)
    if not values:
        raise ValueError(f"the time variable in {nc_path} is empty")
    scale, epoch = parse_cf_units(units)
    lo, hi = min(values), max(values)
    return epoch + timedelta(seconds=lo * scale), epoch + timedelta(seconds=hi * scale)


def _fmt(seconds, tunit):
    v = seconds / TUNIT_SECONDS.get(tunit.upper(), 1.0)
    return str(int(round(v))) if abs(v - round(v)) < 1e-6 else f"{v:.6g}"


def time_settings(nc_path, tunit="S", quiet=False):
    """
    RefDate / TStart / TStop derived from the NetCDF time axis.

    RefDate is midnight of the first time stamp; TStart and TStop are offsets
    from that midnight, expressed in the model's Tunit.

    Args:
        nc_path (Path): Path to the NetCDF forcing file.
        tunit (str): Model time unit, one of S, M, H, D.
        quiet (bool): Suppress non-error output.

    Returns:
        dict: {'RefDate': ..., 'TStart': ..., 'TStop': ...}
    """
    t0, t1 = nc_time_range(nc_path)
    ref = t0.replace(hour=0, minute=0, second=0, microsecond=0)
    _print(
        f"NetCDF time span: {t0:%Y-%m-%d %H:%M:%S} -> {t1:%Y-%m-%d %H:%M:%S}",
        quiet,
    )
    return {
        "RefDate": ref.strftime("%Y%m%d"),
        "TStart": _fmt((t0 - ref).total_seconds(), tunit),
        "TStop": _fmt((t1 - ref).total_seconds(), tunit),
    }


def resolve_forcing_path(nc_file, ext_path):
    """D-Flow FM resolves forcingFile relative to the .ext file, so rewrite a
    path given relative to the cwd (or an absolute one) into that form."""
    nc = Path(nc_file)
    if not nc.exists():
        return nc_file  # nothing to resolve against; write it through as given
    try:
        rel = os.path.relpath(nc.resolve(), Path(ext_path).resolve().parent)
    except ValueError:  # different drive on Windows -> keep the absolute path
        return str(nc.resolve())
    return rel.replace(os.sep, "/")


def set_nc_rainfall(
    nc_file,
    ext_file="dflowfm/FM_model_bnd.ext",
    mdu_file=None,
    update_time=True,
    as_given=False,
    backup=True,
    quiet=False,
):
    """
    Point a D-Flow FM model at a NetCDF rainfall forcing file.

    Args:
        nc_file (str): Path to the NetCDF forcing file.
        ext_file (str): Path to the .ext file (created if missing).
        mdu_file (str): Model definition file; defaults to the *.mdu next to
            the .ext file.
        update_time (bool): Also set RefDate/TStart/TStop from the NetCDF
            time axis.
        as_given (bool): Write the forcingFile path exactly as typed instead
            of making it relative to the .ext file.
        backup (bool): Write .bak copies before overwriting files.
        quiet (bool): Suppress non-error output.

    Returns:
        tuple[Path, Path | None]: Paths to the (.ext, .mdu) touched; the .mdu
        is None when no model definition file could be found.
    """
    nc_path = Path(nc_file)
    ext_path = Path(ext_file)
    forcing = nc_file if as_given else resolve_forcing_path(nc_file, ext_path)

    created = not ext_path.is_file()
    if created:
        _print(f"{ext_path} not found - creating it.", quiet)
        create(ext_path, forcing, quiet=quiet)
    else:
        rewrite(ext_path, forcing, backup=backup, quiet=quiet)

    # ---- model definition file -------------------------------------------
    settings = {}
    if created:
        # a freshly created .ext has to be registered in the .mdu
        settings["ExtForceFileNew"] = ext_path.name

    mdu_path = Path(mdu_file) if mdu_file else find_mdu(ext_path)
    if mdu_path is None:
        print(
            f"! No *.mdu found in {ext_path.parent} - model times not updated.",
            file=sys.stderr,
        )
        return ext_path, None
    if not mdu_path.is_file():
        print(
            f"! mdu not found: {mdu_path} - model times not updated.",
            file=sys.stderr,
        )
        return ext_path, None

    if update_time:
        if not nc_path.is_file():
            print(
                f"! {nc_path} not found - RefDate/TStart/TStop left unchanged.",
                file=sys.stderr,
            )
        else:
            tunit = (read_mdu_value(mdu_path, "Tunit") or "S").upper() or "S"
            try:
                settings.update(time_settings(nc_path, tunit, quiet=quiet))
            except Exception as exc:  # unreadable file, odd time axis, ...
                print(f"! could not read times from {nc_path}: {exc}", file=sys.stderr)
                print("  RefDate/TStart/TStop left unchanged.", file=sys.stderr)

    if settings:
        update_mdu(mdu_path, settings, backup=backup, quiet=quiet)

    return ext_path, mdu_path


def main():
    parser = argparse.ArgumentParser(
        prog='setncrain',
        description='Point a D-Flow FM .ext/.mdu pair at a NetCDF rainfall forcing file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  setncrain -i May28_Event.nc
  setncrain -i C:/data/rain/May28_Event.nc
  setncrain -i May28_Event.nc --ext dflowfm/FM_model_bnd.ext
  setncrain -i May28_Event.nc --no-backup --as-given
        """,
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {importlib.metadata.version("ncftools")}',
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        metavar='FILE',
        help='Path to the NetCDF rainfall forcing file (*.nc)',
    )
    parser.add_argument(
        '--ext',
        default='dflowfm/FM_model_bnd.ext',
        metavar='FILE',
        help='Path to the .ext file (default: dflowfm/FM_model_bnd.ext)',
    )
    parser.add_argument(
        '--mdu',
        metavar='FILE',
        help='Model definition file to update (default: the *.mdu next to the .ext)',
    )
    parser.add_argument(
        '--no-time',
        action='store_true',
        help='Do not touch RefDate/TStart/TStop in the .mdu',
    )
    parser.add_argument(
        '--as-given',
        action='store_true',
        help='Write the path exactly as typed instead of making it relative to the .ext file',
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not write .bak copies',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output',
    )

    args = parser.parse_args()

    if not args.input.lower().endswith('.nc'):
        print("Error: forcing file must be a *.nc file", file=sys.stderr)
        sys.exit(1)

    try:
        ext_path, mdu_path = set_nc_rainfall(
            args.input,
            ext_file=args.ext,
            mdu_file=args.mdu,
            update_time=not args.no_time,
            as_given=args.as_given,
            backup=not args.no_backup,
            quiet=args.quiet,
        )
        if args.quiet:
            print(ext_path)
            if mdu_path is not None:
                print(mdu_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
