"""
Rewrite dflowfm/FM_model_bnd.ext for NetCDF rainfall forcing.

In every [Meteo] block:
    quantity        -> rainfall
    forcingFile     -> <user specified *.nc>
    forcingFileType -> netcdf

If the .ext file does not exist it is created from the contents hard-coded
below (TEMPLATE), already pointing at the given NetCDF file, and
ExtForceFileNew in the model definition file (*.mdu) is set to it.

The NetCDF time axis is always read, and the model times in the .mdu are
adjusted to it:
    RefDate -> the date of the first time stamp (midnight)
    TStart  -> offset of the first time stamp from RefDate (in Tunit)
    TStop   -> offset of the last  time stamp from RefDate (in Tunit)
Needs netCDF4 (or xarray, or scipy) to read the file:  pip install netCDF4

Usage:
    python update_bnd_ext.py -i May28_Event.nc
    python update_bnd_ext.py -i C:/data/rain/May28_Event.nc
    python update_bnd_ext.py May28_Event.nc --ext dflowfm/FM_model_bnd.ext
    python update_bnd_ext.py -i May28_Event.nc --no-backup --as-given
"""

import argparse
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

REPLACEMENTS = {
    "quantity": "rainfall",
    "forcingfiletype": "netcdf",
    # forcingFile is filled in at runtime
}

# Hard-coded .ext contents, used when dflowfm/FM_model_bnd.ext is missing.
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


def create(ext_path: Path, nc_file: str) -> None:
    """Create a new .ext file from the hard-coded TEMPLATE, pointing at nc_file."""
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    # D-Flow FM input files conventionally use CRLF
    with ext_path.open("w", newline="\r\n") as f:
        f.write(TEMPLATE.format(forcing_file=nc_file))
    print(f"Created: {ext_path}")
    print(f"  quantity=rainfall, forcingFile={nc_file}, forcingFileType=netcdf")


def find_mdu(ext_path: Path) -> Optional[Path]:
    """Locate the .mdu next to the .ext file (FM_model.mdu wins if several)."""
    folder = ext_path.parent if str(ext_path.parent) else Path(".")
    mdus = sorted(folder.glob("*.mdu"))
    if not mdus:
        return None
    for m in mdus:
        if m.stem.lower() == "fm_model":
            return m
    return mdus[0]


def read_mdu_value(mdu_path: Path, key: str) -> Optional[str]:
    """Return the value of a single .mdu key, or None if it is absent."""
    with mdu_path.open("r", newline="") as f:
        for line in f:
            name, sep, rest = line.partition("=")
            if sep and name.strip().lower() == key.lower():
                return rest.partition("#")[0].strip()
    return None


def update_mdu(mdu_path: Path, settings: dict, backup: bool = True) -> None:
    """Set the given key=value pairs in the .mdu, preserving layout and comments."""
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
            print(f"! {label} not found in {mdu_path} - set it to {value} manually.")

    if not changed:
        print(f"{mdu_path}: already up to date.")
        return

    if backup:
        bak = mdu_path.with_suffix(mdu_path.suffix + ".bak")
        shutil.copy2(mdu_path, bak)
        print(f"Backup written: {bak}")

    with mdu_path.open("w", newline="") as f:
        f.write("".join(out))
    print(f"Updated: {mdu_path}")
    for c in changed:
        print(f"  {c}")


def rewrite(ext_path: Path, nc_file: str, backup: bool = True) -> None:
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
                # keep original spacing style around '='
                lead = old_val[: len(old_val) - len(old_val.lstrip())]
                trail = "" if sep else old_val[len(old_val.rstrip()):]
                body = f"{key}={lead}{new_val}{trail}{sep}{comment}"
                changed.append(f"{key.strip()} = {old_val.strip()} -> {new_val}")
                line = body + eol

        out.append(line)

    if not changed:
        print("No [Meteo] keys matched - file left unchanged.")
        return

    if backup:
        bak = ext_path.with_suffix(ext_path.suffix + ".bak")
        shutil.copy2(ext_path, bak)
        print(f"Backup written: {bak}")

    with ext_path.open("w", newline="") as f:
        f.write("".join(out))

    print(f"Updated: {ext_path}")
    for c in changed:
        print(f"  {c}")


CF_UNITS = {
    "second": 1.0, "seconds": 1.0, "sec": 1.0, "secs": 1.0, "s": 1.0,
    "minute": 60.0, "minutes": 60.0, "min": 60.0, "mins": 60.0,
    "hour": 3600.0, "hours": 3600.0, "hr": 3600.0, "hrs": 3600.0, "h": 3600.0,
    "day": 86400.0, "days": 86400.0, "d": 86400.0,
}
# TStart/TStop are expressed in the model's Tunit
TUNIT_SECONDS = {"S": 1.0, "M": 60.0, "H": 3600.0, "D": 86400.0}


def _open_time_var(nc_path: Path):
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
            get = lambda n, a: getattr(ds.variables[n], a, None)
            name = pick(list(ds.variables), get)
            if name is None:
                raise ValueError(f"no time variable found in {nc_path}")
            v = ds.variables[name]
            return [float(x) for x in v[:].ravel()], str(getattr(v, "units", ""))

    try:
        import xarray  # noqa: F401  (second choice)
    except ImportError:
        pass
    else:
        import xarray as xr

        with xr.open_dataset(str(nc_path), decode_times=False) as ds:
            get = lambda n, a: ds[n].attrs.get(a)
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
        get = lambda n, a: (
            getattr(ds.variables[n], a, b"").decode()
            if isinstance(getattr(ds.variables[n], a, None), bytes)
            else getattr(ds.variables[n], a, None)
        )
        name = pick(list(ds.variables), get)
        if name is None:
            raise ValueError(f"no time variable found in {nc_path}")
        v = ds.variables[name]
        units = getattr(v, "units", b"")
        return (
            [float(x) for x in v[:].ravel()],
            units.decode() if isinstance(units, bytes) else str(units),
        )


def parse_cf_units(units: str):
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


def nc_time_range(nc_path: Path):
    """First and last time stamp in the NetCDF file, as datetimes."""
    values, units = _open_time_var(nc_path)
    if not values:
        raise ValueError(f"the time variable in {nc_path} is empty")
    scale, epoch = parse_cf_units(units)
    lo, hi = min(values), max(values)
    return epoch + timedelta(seconds=lo * scale), epoch + timedelta(seconds=hi * scale)


def _fmt(seconds: float, tunit: str) -> str:
    v = seconds / TUNIT_SECONDS.get(tunit.upper(), 1.0)
    return str(int(round(v))) if abs(v - round(v)) < 1e-6 else f"{v:.6g}"


def time_settings(nc_path: Path, tunit: str = "S") -> dict:
    """RefDate / TStart / TStop derived from the NetCDF time axis.

    RefDate is midnight of the first time stamp; TStart and TStop are offsets
    from that midnight, expressed in the model's Tunit.
    """
    t0, t1 = nc_time_range(nc_path)
    ref = t0.replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"NetCDF time span: {t0:%Y-%m-%d %H:%M:%S} -> {t1:%Y-%m-%d %H:%M:%S}")
    return {
        "RefDate": ref.strftime("%Y%m%d"),
        "TStart": _fmt((t0 - ref).total_seconds(), tunit),
        "TStop": _fmt((t1 - ref).total_seconds(), tunit),
    }


def resolve_forcing_path(nc_file: str, ext_path: Path) -> str:
    """D-Flow FM resolves forcingFile relative to the .ext file, so rewrite a
    path given relative to the cwd (or an absolute one) into that form."""
    nc = Path(nc_file)
    if not nc.exists():
        return nc_file  # nothing to resolve against; write it through as given
    try:
        rel = os.path.relpath(nc.resolve(), ext_path.resolve().parent)
    except ValueError:  # different drive on Windows -> keep the absolute path
        return str(nc.resolve())
    return rel.replace(os.sep, "/")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Point FM_model_bnd.ext at a NetCDF rainfall forcing file."
    )
    p.add_argument(
        "nc_file_pos",
        nargs="?",
        metavar="NC_FILE",
        help="NetCDF forcing file (positional form of -i)",
    )
    p.add_argument(
        "-i",
        "--input-file",
        dest="input_file",
        help="path to the NetCDF forcing file, e.g. -i data/May28_Event.nc",
    )
    p.add_argument(
        "--ext",
        default="dflowfm/FM_model_bnd.ext",
        help="path to the .ext file (default: dflowfm/FM_model_bnd.ext)",
    )
    p.add_argument(
        "--mdu",
        help="model definition file to update "
        "(default: the *.mdu sitting next to the .ext)",
    )
    p.add_argument(
        "--no-time",
        action="store_true",
        help="do not touch RefDate/TStart/TStop in the .mdu",
    )
    p.add_argument(
        "--as-given",
        action="store_true",
        help="write the path exactly as typed instead of making it relative to the .ext file",
    )
    p.add_argument("--no-backup", action="store_true", help="do not write a .bak copy")
    args = p.parse_args()

    nc_file = nc_file_in = args.input_file or args.nc_file_pos
    if not nc_file:
        p.error("no forcing file given; use -i/--input-file PATH")
    if args.input_file and args.nc_file_pos:
        p.error("give the forcing file either positionally or with -i, not both")
    if not nc_file.lower().endswith(".nc"):
        p.error("forcing file must be a *.nc file")

    nc_path = Path(nc_file_in)
    ext_path = Path(args.ext)
    if not args.as_given:
        nc_file = resolve_forcing_path(nc_file, ext_path)

    created = not ext_path.is_file()
    if created:
        print(f"{ext_path} not found - creating it.")
        create(ext_path, nc_file)
    else:
        rewrite(ext_path, nc_file, backup=not args.no_backup)

    # ---- model definition file -------------------------------------------
    settings = {}
    if created:
        # a freshly created .ext has to be registered in the .mdu
        settings["ExtForceFileNew"] = ext_path.name

    mdu_path = Path(args.mdu) if args.mdu else find_mdu(ext_path)
    if mdu_path is None:
        print(f"! No *.mdu found in {ext_path.parent} - model times not updated.")
        return
    if not mdu_path.is_file():
        print(f"! mdu not found: {mdu_path} - model times not updated.")
        return

    if not args.no_time:
        if not nc_path.is_file():
            print(f"! {nc_path} not found - RefDate/TStart/TStop left unchanged.")
        else:
            tunit = (read_mdu_value(mdu_path, "Tunit") or "S").upper() or "S"
            try:
                settings.update(time_settings(nc_path, tunit))
            except Exception as exc:  # unreadable file, odd time axis, ...
                print(f"! could not read times from {nc_path}: {exc}")
                print("  RefDate/TStart/TStop left unchanged.")

    if settings:
        update_mdu(mdu_path, settings, backup=not args.no_backup)


if __name__ == "__main__":
    main()
