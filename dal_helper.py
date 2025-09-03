"""
This file is shared among all most of my export scripts and contains various boilerplaty stuff.

If you know how to make any of this easier, please let me know!
"""

from __future__ import annotations

__all__ = [
    'Json',
    'PathIsh',
    'Res',
    'pathify',
    'the',
]

import argparse
import sys
import warnings
from collections.abc import Iterator
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, TypeAlias, TypeVar

PathIsh = str | Path


def pathify(path: PathIsh) -> Path:
    """
    Helper mainly to support CPath hack
    See https://github.com/karlicoss/HPI/blob/be21606075cbc15018d1f36c2581ab138e4a44cc/tests/misc.py#L29-L32
    Otherwise if we do Path(CPath(...)), it will ruin the decompression hack
    """
    if isinstance(path, Path):
        return path
    else:
        return Path(path)


Json = dict[str, Any]  # todo Mapping?


T = TypeVar('T')
Res: TypeAlias = T | Exception


def make_parser(*, single_source: bool = False, package: str | None = None) -> argparse.ArgumentParser:
    # meh..
    if package is None:
        assert __package__ is not None
        pkg = __package__.split('.')[0]
    else:
        pkg = package

    p = argparse.ArgumentParser(
        'DAL (Data Access/Abstraction Layer)',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100),
    )
    source_help = 'Path to exported data'
    if not single_source:
        source_help += ". Can be single file, or a glob, e.g. '/path/to/exports/*.ext'"

    p.add_argument(
        '--source',
        type=str,
        required=True,
        help=source_help,
    )
    # todo link to exports post why multiple exports could be useful
    if not single_source:
        p.add_argument('--no-glob', action='store_true', help='Treat path in --source literally')
    p.add_argument('-i', '--interactive', action='store_true', help='Start Ipython session to play with data')

    p.epilog = f"""
You can use `{pkg}.dal` (stands for "Data Access/Abstraction Layer") to access your exported data, even offline.
I elaborate on motivation behind it [here](https://beepb00p.xyz/exports.html#dal).

- main usecase is to be imported as python module to allow for **programmatic access** to your data.

  You can find some inspiration in [`my.`](https://beepb00p.xyz/mypkg.html) package that I'm using as an API to all my personal data.

- to test it against your export, simply run: `python3 -m {pkg}.dal --source /path/to/export`

- you can also try it interactively in an Ipython shell: `python3 -m {pkg}.dal --source /path/to/export --interactive`

"""
    return p


def main(*, DAL, demo=None, single_source=False) -> None:
    """
    single_source: used when exports are not cumulative/synthetic
    (you can find out more about it here: https://beepb00p.xyz/exports.html#types)
    """
    p = make_parser(single_source=single_source)
    args = p.parse_args()

    if single_source:
        dal = DAL(args.source)
    else:
        if '*' in args.source and not args.no_glob:
            sources = glob(args.source)  # noqa: PTH207
        else:
            ps = Path(args.source)
            if ps.is_dir():
                sources = sorted(ps.iterdir())  # hopefully, makes sense?
            else:
                sources = [ps]
        dal = DAL(sources)
    # logger.debug('using %s', sources)

    print(dal)
    # TODO autoreload would be nice... https://github.com/ipython/ipython/issues/1144
    # TODO maybe just launch through ipython in the first place?
    if args.interactive:
        import IPython  # type: ignore[import-not-found]

        IPython.embed(header="Feel free to mess with 'dal' object in the interactive shell")
    else:
        assert demo is not None, "No 'demo' in 'dal.py'?"
        demo(dal)


# legacy: logger function used to be in this file

from collections.abc import Iterable


# todo rename to only, like in more_itertools?
# although it's not exactly the same, i.e. also checks that they are all equal..
# and turning to a set() isn't always an option because it's a hash set
def the(l: Iterable[T]) -> T:
    it = iter(l)
    try:
        first = next(it)
    except StopIteration:
        raise RuntimeError('Empty iterator?')  # noqa: B904
    assert all(e == first for e in it)
    return first


datetime_naive = datetime  # for now just an alias
datetime_aware = datetime  # for now just an alias


def json_items(p: Path, key: str | None) -> Iterator[Json]:
    # if key is None, means we expect list on the top level

    # todo perhaps add to setup.py as 'optional' or 'faster'?
    try:
        import ijson  # type: ignore[import-untyped]
        # todo would be nice to debug output the backend?
    except ModuleNotFoundError as e:
        if e.name != 'ijson':
            # this may happen if the user requested a specific ijson backend (e.g. via IJSON_BACKEND)
            # worth being non-defensive in that case
            raise e
        warnings.warn("recommended to 'pip install ijson' for faster json processing", stacklevel=3)
    else:
        extractor = 'item' if key is None else f'{key}.item'
        with p.open(mode='rb') as fo:
            yield from ijson.items(fo, extractor, use_float=True)
        return

    try:
        import orjson
    except ModuleNotFoundError as e:
        if e.name != 'orjson':
            raise e
        warnings.warn("recommended to 'pip install orjson' for faster json processing", stacklevel=3)
    else:
        j = orjson.loads(p.read_text())
        if key is not None:
            j = j[key]
        yield from j
        return

    # otherwise just fall back onto regular json
    import json

    j = json.loads(p.read_text())
    if key is not None:
        j = j[key]
    yield from j


if sys.version_info[:2] >= (3, 11):
    fromisoformat = datetime.fromisoformat
else:
    # fromisoformat didn't support Z as "utc" before 3.11
    # https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat

    def fromisoformat(date_string: str) -> datetime:
        if date_string.endswith('Z'):
            date_string = date_string[:-1] + '+00:00'
        return datetime.fromisoformat(date_string)
