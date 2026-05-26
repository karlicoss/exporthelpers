from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from .export_helper import Parser, setup_parser


def make_legacy_test_parser(*, params: list[str]) -> argparse.ArgumentParser:
    parser = Parser('test exporter')
    setup_parser(parser=parser, params=params, package='example')
    return parser


def make_test_parser(*, params: list[str]) -> argparse.ArgumentParser:
    return Parser('test exporter', params=params, package='example')


def make_legacy_help_parser(*args, **kwargs) -> argparse.ArgumentParser:
    return Parser(*args, **kwargs)


def make_help_parser(*args, **kwargs) -> argparse.ArgumentParser:
    return Parser(*args, params=[], **kwargs)


# Export parser factories cover both supported setup styles:
# - make_legacy_test_parser: legacy `Parser(...)` followed by `setup_parser(...)`
# - make_test_parser: new direct `Parser(..., params=[...])`
EXPORT_PARSER_FACTORIES = [make_legacy_test_parser, make_test_parser]

HELP_PARSER_FACTORIES = [make_legacy_help_parser, make_help_parser]


@pytest.mark.parametrize('parser_factory', HELP_PARSER_FACTORIES)
def test_parser_help_preserves_manual_formatting(parser_factory) -> None:
    description = 'first line\n\n    indented line\nsecond line'
    parser = parser_factory('test exporter', description=description)

    help_text = parser.format_help()

    assert description in help_text


@pytest.mark.parametrize('parser_factory', HELP_PARSER_FACTORIES)
def test_parser_help_preserves_wide_lines(parser_factory) -> None:
    description = ' '.join(['word'] * 18)
    assert len(description) == 89
    parser = parser_factory('test exporter', description=description)

    help_text = parser.format_help()

    assert description in help_text


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_reads_params_from_secrets_file(make_parser, tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('username = "alice"\npassword = "secret"\n')

    args = make_parser(params=['username', 'password']).parse_args(['--secrets', str(secrets)])

    assert args.params == {
        'username': 'alice',
        'password': 'secret',
    }


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_reads_multiple_params_from_command_line(make_parser) -> None:
    args = make_parser(params=['username', 'password']).parse_args(
        [
            '--username',
            'alice',
            '--password',
            'secret',
        ]
    )

    assert args.params == {
        'username': 'alice',
        'password': 'secret',
    }


def parse_error(
    parser: argparse.ArgumentParser,
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> str:
    with pytest.raises(SystemExit) as e:
        parser.parse_args(argv)

    assert e.value.code == 2
    return capsys.readouterr().err


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_rejects_mixing_secrets_file_and_command_line_params(
    make_parser,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('token = "SECRET"\n')

    error = parse_error(
        make_parser(params=['token']),
        ['--secrets', str(secrets), '--token', 'TOKEN'],
        capsys,
    )

    assert 'Please use either --secrets file or individual --param arguments' in error


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_missing_param_warning_lists_only_missing_params(make_parser) -> None:
    with pytest.warns(UserWarning, match='Missing API parameters: password'):
        args = make_parser(params=['username', 'password']).parse_args(['--username', 'alice'])

    assert args.params == {'username': 'alice'}


def test_direct_parser_strict_missing_params_are_parse_errors(capsys: pytest.CaptureFixture[str]) -> None:
    # Direct Parser setup defaults to the legacy warning behavior above. `strict=True` opts into
    # treating missing params as CLI usage errors for callers that are ready for it.
    error = parse_error(
        Parser('test exporter', params=['username', 'password'], package='example', strict=True),
        ['--username', 'alice'],
        capsys,
    )

    assert 'Missing API parameters: password' in error


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_secrets_error_does_not_print_loaded_values(
    make_parser,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('username = "alice"\ntoken = "SENSITIVE_VALUE"\n')

    error = parse_error(
        make_parser(params=['username', 'password']),
        ['--secrets', str(secrets)],
        capsys,
    )

    assert f"Couldn't extract API parameters from file {secrets}: password" in error
    assert 'alice' not in error
    assert 'SENSITIVE_VALUE' not in error


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_default_dumper_writes_to_stdout(make_parser, capsys: pytest.CaptureFixture[str]) -> None:
    args = make_parser(params=['token']).parse_args(['--token', 'SECRET'])

    args.dumper('{"ok": true}')

    captured = capsys.readouterr()
    assert captured.out == '{"ok": true}'
    assert captured.err == ''


@pytest.mark.parametrize('make_parser', EXPORT_PARSER_FACTORIES)
def test_output_path_dumper_writes_file_and_reports_path(
    make_parser,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / 'export.json'

    args = make_parser(params=['token']).parse_args(['--token', 'SECRET', str(output)])
    args.dumper('{"ok": true}')

    assert output.read_text() == '{"ok": true}'
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == f'saved data to {output}\n'
