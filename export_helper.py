from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

Json = dict[str, Any]


def Parser(*args, **kwargs) -> argparse.ArgumentParser:
    # just more reasonable default for literate usage
    return argparse.ArgumentParser( # type: ignore[misc]
        *args,
        formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=100),
        **kwargs,
    )


def setup_parser(parser: argparse.ArgumentParser, *, params: Sequence[str], extra_usage: str | None=None, package: str | None=None) -> None:
    # meh..
    pkg = __package__.split('.')[0] if package is None else package

    PARAMS_KEY = 'params'
    set_from_file = False
    set_from_cmdl = False

    use_secrets = RuntimeError("Please use either --secrets file or individual --param arguments (see --help)")
    class SetParamsFromFile(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # noqa: ARG002
            if set_from_cmdl:
                raise use_secrets
            nonlocal set_from_file; set_from_file = True

            secrets_file = values
            obj: dict[str, Any] = {}

            # we control the file with secrets so exec is fine
            exec(secrets_file.read_text(), {}, obj)

            def get(k):
                if k not in obj:
                    raise RuntimeError(f"Couldn't extract '{k}' param from file {secrets_file} (got {obj})")
                return obj[k]

            pdict = {k: get(k) for k in params}
            setattr(namespace, PARAMS_KEY, pdict)

    class SetParam(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # noqa: ARG002
            if set_from_file:
                raise use_secrets
            nonlocal set_from_cmdl; set_from_cmdl = True

            pdict = getattr(namespace, PARAMS_KEY, {})
            pdict[self.dest] = values
            setattr(namespace, PARAMS_KEY, pdict)

    class SetOutput(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # noqa: ARG002
            output_path = values

            def dump_to_stdout(data):
                sys.stdout.write(data)

            def dump_to_file(data):
                with output_path.open('w', encoding='utf-8') as fo:
                    fo.write(data)
                print(f'saved data to {output_path}', file=sys.stderr)

            if output_path is None:
                dumper = dump_to_stdout
            else:
                dumper = dump_to_file

            setattr(namespace, 'dumper', dumper)

    paramss = ' '.join(f'--{p} <{p}>' for p in params)

    sep = '\n: '
    secrets_example = sep + sep.join(f'{p} = "{p.upper()}"' for p in params)

    parser.epilog = f'''
Usage:

*Recommended*: create =secrets.py= keeping your api parameters, e.g.:

{secrets_example}


After that, use:

: python3 -m {pkg}.export --secrets /path/to/secrets.py

That way you type less and have control over where you keep your plaintext secrets.

*Alternatively*, you can pass parameters directly, e.g.

: python3 -m {pkg}.export {paramss}

However, this is verbose and prone to leaking your keys/tokens/passwords in shell history.

    '''

    if extra_usage is not None:
        parser.epilog += extra_usage

    parser.epilog += '''

I *highly* recommend checking exported files at least once just to make sure they contain everything you expect from your export. If not, please feel free to ask or raise an issue!
    '''

    parser.add_argument(
        '--secrets',
        metavar='SECRETS_FILE',
        type=Path,
        action=SetParamsFromFile,
        required=False,
        help='.py file containing API parameters',
    )
    gr = parser.add_argument_group('API parameters')
    for param in params:
        gr.add_argument('--' + param, type=str, action=SetParam)


    # hack to avoid cryptic error messages when you forget to specify secrets file/cmdline args
    # ok, judging by argparse code, it's safe to assume this will be called at the very end
    # https://github.com/python/cpython/blob/9c4eac7f02ddcf32fc1cdaf7c08c37fe9718c1fb/Lib/argparse.py#L2068-L2079
    def check_params(*_args):
        if not set_from_file and not set_from_cmdl:
            raise use_secrets
    # todo would be nice to omit if from help
    parser.add_argument('--check-params-hook', type=check_params, default='', help="internal argument, please don't use")

    parser.add_argument(
        'path',
        type=Path,
        action=SetOutput,
        nargs='?',
        help='Optional path where exported data will be dumped, otherwise printed to stdout',
    )

# legacy: function used to be in this file
if not TYPE_CHECKING:
    from .logging_helper import logger  # noqa: F401
