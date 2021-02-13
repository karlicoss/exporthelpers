"""
This file is shared among all most of my export scripts and contains various boilerplaty stuff.

If you know how to make any of this easier, please let me know!
"""

__all__ = [
    'PathIsh',
    'Json',
    'Res',
    'the',
]

import argparse
from glob import glob
from pathlib import Path
from typing import Any, Dict, Union, TypeVar, Optional

PathIsh = Union[str, Path]
Json = Dict[str, Any] # todo Mapping?


T = TypeVar('T')
Res = Union[T, Exception]


def make_parser(single_source=False, package: Optional[str]=None) -> argparse.ArgumentParser:
    # meh..
    pkg = __package__.split('.')[0] if package is None else package

    p = argparse.ArgumentParser(
        'DAL (Data Access/Abstraction Layer)',
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100), # type: ignore
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
        p.add_argument(
            '--no-glob',
            action='store_true',
            help='Treat path in --source literally'
        )
    p.add_argument('-i', '--interactive', action='store_true', help='Start Ipython session to play with data')

    p.epilog = f"""
You can use ={pkg}.dal= (stands for "Data Access/Abstraction Layer") to access your exported data, even offline.
I elaborate on motivation behind it [[https://beepb00p.xyz/exports.html#dal][here]].

- main usecase is to be imported as python module to allow for *programmatic access* to your data.

  You can find some inspiration in [[https://beepb00p.xyz/mypkg.html][=my.=]] package that I'm using as an API to all my personal data.

- to test it against your export, simply run: ~python3 -m {pkg}.dal --source /path/to/export~

- you can also try it interactively: ~python3 -m {pkg}.dal --source /path/to/export --interactive~

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
            sources = glob(args.source)
        else:
            ps = Path(args.source)
            if ps.is_dir():
                sources = list(sorted(ps.iterdir())) # hopefully, makes sense?
            else:
                sources = [ps]
        dal = DAL(sources)
    # logger.debug('using %s', sources)

    print(dal)
    # TODO autoreload would be nice... https://github.com/ipython/ipython/issues/1144
    # TODO maybe just launch through ipython in the first place?
    if args.interactive:
        import IPython # type: ignore
        IPython.embed(header="Feel free to mess with 'dal' object in the interactive shell")
    else:
        assert demo is not None, "No 'demo' in 'dal.py'?"
        demo(dal)

# legacy: logger function used to be in this file
from .logging_helper import logger

from typing import Iterable
# todo rename to only, like in more_itertools?
# although it's not exactly the same, i.e. also checks that they are all equal..
# and turning to a set() isn't always an option because it's a hash set
def the(l: Iterable[T]) -> T:
    it = iter(l)
    try:
        first = next(it)
    except StopIteration as ee:
        raise RuntimeError('Empty iterator?')
    assert all(e == first for e in it)
    return first

from datetime import datetime
datetime_naive = datetime # for now just an alias
datetime_aware = datetime # for now just an alias
