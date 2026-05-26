from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, overload

Json = dict[str, Any]
Dumper = Callable[[str], None]

_PARAMS_KEY = 'params'
_UNSET = object()


def _package_name(package: str | None) -> str:
    # meh.. this is only for help examples; callers can pass package explicitly if this heuristic fails.
    if package is None:
        assert __package__ is not None
        return __package__.split('.')[0]
    else:
        return package


def _export_epilog(*, params: Sequence[str], pkg: str, extra_usage: str | None) -> str:
    paramss = ' '.join(f'--{p} <{p}>' for p in params)

    sep = '\n    '
    secrets_example = sep + sep.join(f'{p} = "{p.upper()}"' for p in params)

    epilog = f'''
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
        epilog += extra_usage

    epilog += '''

I **highly** recommend checking exported files at least once just to make sure they contain everything you expect from your export
If they don't, please feel free to ask or raise an issue!
    '''
    return epilog


def _make_dumper(output_path: Path | None) -> Dumper:
    def dump_to_stdout(data: str) -> None:
        sys.stdout.write(data)

    def dump_to_file(data: str) -> None:
        assert output_path is not None
        output_path.write_text(data)
        print(f'saved data to {output_path}', file=sys.stderr)

    if output_path is None:
        return dump_to_stdout
    else:
        return dump_to_file


class Parser(argparse.ArgumentParser):
    """
    ArgumentParser with optional export-helper setup.

    Old style can construct `Parser(...)` and call `setup_parser(...)` later.
    New style can construct `Parser(..., params=[...])` directly.
    """

    def __init__(
        self,
        *args,
        params: Any = _UNSET,
        extra_usage: str | None = None,
        package: str | None = None,
        strict: bool = False,
        **kwargs,
    ) -> None:
        # just more reasonable default for literate usage
        if 'formatter_class' not in kwargs:
            kwargs['formatter_class'] = lambda prog: argparse.RawTextHelpFormatter(prog, width=100)
        super().__init__(*args, **kwargs)

        self._export_params: tuple[str, ...] | None = None
        self._export_strict = strict
        if params is not _UNSET:
            self.setup_export(params=params, extra_usage=extra_usage, package=package, strict=strict)

    def setup_export(
        self,
        *,
        params: Sequence[str],
        extra_usage: str | None = None,
        package: str | None = None,
        strict: bool = False,
    ) -> None:
        if self._export_params is not None:
            raise RuntimeError('export parser is already configured')

        self._export_params = tuple(params)
        self._export_strict = strict
        self.set_defaults(**{_PARAMS_KEY: {}})

        pkg = _package_name(package)
        self.epilog = _export_epilog(params=params, pkg=pkg, extra_usage=extra_usage)

        self.add_argument(
            '--secrets',
            metavar='SECRETS_FILE',
            type=Path,
            required=False,
            help='.py file containing API parameters',
        )
        gr = self.add_argument_group('API parameters')
        for param in params:
            gr.add_argument('--' + param, type=str)

        self.add_argument(
            'path',
            type=Path,
            nargs='?',
            help='Optional path where exported data will be dumped, otherwise printed to stdout',
        )

    @overload
    def parse_args(self, args: Iterable[str] | None = None, namespace: None = None) -> argparse.Namespace: ...

    @overload
    def parse_args[N](self, args: Iterable[str] | None, namespace: N) -> N: ...

    @overload
    def parse_args[N](self, *, namespace: N) -> N: ...

    def parse_args(self, args: Iterable[str] | None = None, namespace: Any = None) -> Any:
        namespace = super().parse_args(args, namespace)
        self._finalize_export_namespace(namespace)
        return namespace

    def _finalize_export_namespace(self, namespace: Any) -> None:
        params = self._export_params
        if params is None:
            return

        secrets_file: Path | None = getattr(namespace, 'secrets')
        cmdline_params = {p: getattr(namespace, p) for p in params if getattr(namespace, p) is not None}
        if secrets_file is not None and len(cmdline_params) > 0:
            self.error("Please use either --secrets file or individual --param arguments (see --help)")

        if secrets_file is None:
            params_dict = cmdline_params
        else:
            params_dict = self._read_params_from_file(secrets_file)

        missing_params = [p for p in params if p not in params_dict]
        if len(missing_params) > 0:
            msg = f"Missing API parameters: {', '.join(missing_params)}"
            if self._export_strict:
                self.error(msg)
            else:
                warnings.warn(
                    f"""
    {msg}
    This might cause issues with export (see README for setup instructions).
""".rstrip(),
                    stacklevel=3,
                )

        setattr(namespace, _PARAMS_KEY, params_dict)
        setattr(namespace, 'dumper', _make_dumper(getattr(namespace, 'path')))

    def _read_params_from_file(self, secrets_file: Path) -> dict[str, Any]:
        params = self._export_params
        assert params is not None

        obj: dict[str, Any] = {}
        # we control the file with secrets so exec is fine
        exec(secrets_file.read_text(), {}, obj)

        missing_params = [p for p in params if p not in obj]
        if len(missing_params) > 0:
            self.error(f"Couldn't extract API parameters from file {secrets_file}: {', '.join(missing_params)}")

        return {p: obj[p] for p in params}


def setup_parser(
    parser: argparse.ArgumentParser,
    *,
    params: Sequence[str],
    extra_usage: str | None = None,
    package: str | None = None,
    strict: bool = False,
) -> None:
    if not isinstance(parser, Parser):
        raise TypeError('setup_parser expects a parser created with export_helper.Parser')

    parser.setup_export(
        params=params,
        extra_usage=extra_usage,
        package=package,
        strict=strict,
    )
