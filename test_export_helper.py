from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from .export_helper import Parser, setup_parser


def make_test_parser(*, params: list[str]) -> argparse.ArgumentParser:
    parser = Parser('test exporter')
    setup_parser(parser=parser, params=params, package='example')
    return parser


def test_parser_help_preserves_manual_formatting() -> None:
    description = 'first line\n\n    indented line\nsecond line'
    parser = Parser('test exporter', description=description)

    help_text = parser.format_help()

    assert description in help_text


def test_parser_help_preserves_wide_lines() -> None:
    description = ' '.join(['word'] * 18)
    assert len(description) == 89
    parser = Parser('test exporter', description=description)

    help_text = parser.format_help()

    assert description in help_text


def test_reads_params_from_secrets_file(tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('username = "alice"\npassword = "secret"\n')

    args = make_test_parser(params=['username', 'password']).parse_args(['--secrets', str(secrets)])

    assert args.params == {
        'username': 'alice',
        'password': 'secret',
    }


def test_reads_multiple_params_from_command_line() -> None:
    args = make_test_parser(params=['username', 'password']).parse_args(
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


def test_rejects_mixing_secrets_file_and_command_line_params(tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('token = "SECRET"\n')

    with pytest.raises(RuntimeError, match='Please use either --secrets file or individual --param arguments'):
        make_test_parser(params=['token']).parse_args(['--secrets', str(secrets), '--token', 'TOKEN'])


def test_missing_param_warning_lists_only_missing_params() -> None:
    with pytest.warns(UserWarning, match='Missing API parameters: password'):
        args = make_test_parser(params=['username', 'password']).parse_args(['--username', 'alice'])

    assert args.params == {'username': 'alice'}


def test_secrets_error_does_not_require_argparse_system_exit(tmp_path: Path) -> None:
    secrets = tmp_path / 'secrets.py'
    secrets.write_text('other = "value"\n')

    with pytest.raises(RuntimeError, match=re.escape(f"Couldn't extract 'token' param from file {secrets}")):
        make_test_parser(params=['token']).parse_args(['--secrets', str(secrets)])


def test_default_dumper_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    args = make_test_parser(params=['token']).parse_args(['--token', 'SECRET'])

    args.dumper('{"ok": true}')

    captured = capsys.readouterr()
    assert captured.out == '{"ok": true}'
    assert captured.err == ''


def test_output_path_dumper_writes_file_and_reports_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / 'export.json'

    args = make_test_parser(params=['token']).parse_args(['--token', 'SECRET', str(output)])
    args.dumper('{"ok": true}')

    assert output.read_text() == '{"ok": true}'
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == f'saved data to {output}\n'
