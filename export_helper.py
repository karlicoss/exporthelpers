from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def Parser(*args, **kwargs) -> argparse.ArgumentParser:
    # just more reasonable default for literate usage
    if 'formatter_class' not in kwargs:
        kwargs['formatter_class'] = lambda prog: argparse.RawTextHelpFormatter(prog, width=100)
    return argparse.ArgumentParser(*args, **kwargs)


def setup_parser(
    parser: argparse.ArgumentParser,
    *,
    params: Sequence[str],
    extra_usage: str | None = None,
    package: str | None = None,
) -> None:
    # meh..
    if package is None:
        assert __package__ is not None
        pkg = __package__.split('.')[0]
    else:
        pkg = package

    PARAMS_KEY = 'params'
    parser.set_defaults(**{PARAMS_KEY: {}})

    set_from_file = False
    set_from_cmdl = False

    use_secrets = RuntimeError("Please use either --secrets file or individual --param arguments (see --help)")

    class SetParamsFromFile(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):  # noqa: ARG002
            if set_from_cmdl:
                raise use_secrets
            nonlocal set_from_file
            set_from_file = True

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
            nonlocal set_from_cmdl
            set_from_cmdl = True

            pdict = getattr(namespace, PARAMS_KEY, {})
            pdict[self.dest] = values
            setattr(namespace, PARAMS_KEY, pdict)

    def _check_params(namespace: argparse.Namespace) -> None:
        if set_from_cmdl and set_from_file:
            raise use_secrets

        # hack to avoid cryptic error messages when you forget to specify secrets file/cmdline args # ok, judging by argparse code, it's safe to assume this will be called at the very end
        # https://github.com/python/cpython/blob/9c4eac7f02ddcf32fc1cdaf7c08c37fe9718c1fb/Lib/argparse.py#L2068-L2079
        params_dict = getattr(namespace, PARAMS_KEY)
        missing_params = sorted(set(params) - params_dict.keys())
        if len(missing_params) > 0:
            warnings.warn(
                f"""
    Missing API parameters: {', '.join(missing_params)}
    This might cause issues with export (see README for setup instructions).
""".rstrip(),
                stacklevel=2,
            )

    class SetOutput(argparse.Action):
        def __call__(self, parser, namespace: argparse.Namespace, values, option_string=None) -> None:  # noqa: ARG002
            # Kind of nasty to do it here.. but doesn't look like there is anywhere else in argparse we can hook to?
            # And seems that Action for positional args are called even when nothing is passed?
            _check_params(namespace)

            output_path = values

            def dump_to_stdout(data: str) -> None:
                sys.stdout.write(data)

            def dump_to_file(data: str) -> None:
                with output_path.open('w', encoding='utf-8') as fo:
                    fo.write(data)
                print(f'saved data to {output_path}', file=sys.stderr)

            if output_path is None:
                dumper = dump_to_stdout
            else:
                dumper = dump_to_file

            setattr(namespace, 'dumper', dumper)

    paramss = ' '.join(f'--{p} <{p}>' for p in params)

    sep = '\n    '
    secrets_example = sep + sep.join(f'{p} = "{p.upper()}"' for p in params)

    parser.epilog = f'''
Usage:

**Recommended**: create `secrets.py` keeping your API parameters, e.g.:

{secrets_example}


After that, use:

    python3 -m {pkg}.export --secrets /path/to/secrets.py

That way you type less and have control over where you keep your plaintext secrets.

**Alternatively**, you can pass parameters directly, e.g.

    python3 -m {pkg}.export {paramss}

However, this is verbose and prone to leaking your keys/tokens/passwords in shell history.

'''

    if extra_usage is not None:
        parser.epilog += extra_usage

    parser.epilog += '''

I **highly** recommend checking exported files at least once just to make sure they contain everything you expect from your export
If they don't, please feel free to ask or raise an issue!
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

    parser.add_argument(
        'path',
        type=Path,
        action=SetOutput,
        nargs='?',
        help='Optional path where exported data will be dumped, otherwise printed to stdout',
    )
