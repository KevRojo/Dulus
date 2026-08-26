import os
import sys
from unittest.mock import patch
from pathlib import Path
import pytest

from context import resolve_shell_environment, _detect_shell_type, get_platform_hints
from tools import _win_to_posix


def test_posix_shell_detection_on_unix():
    with patch('sys.platform', 'darwin'):
        with patch.dict(os.environ, {'SHELL': '/bin/zsh'}):
            info = resolve_shell_environment({})
            assert info['kind'] == 'bash'
            assert info['family'] == 'bash'
            assert _detect_shell_type({}) == 'bash'


def test_windows_auto_detection_with_gitbash(monkeypatch):
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('context._find_git_bash_path', lambda: r'C:\Program Files\Git\bin\bash.exe')
    monkeypatch.setattr('context._find_powershell_path', lambda: r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
    monkeypatch.setattr('context._detect_running_parent_shell', lambda: None)

    monkeypatch.setenv('PSModulePath', r'C:\Program Files\WindowsPowerShell\Modules')
    monkeypatch.delenv('MSYSTEM', raising=False)
    monkeypatch.delenv('PSExecutionPolicyPreference', raising=False)

    info = resolve_shell_environment({'shell': {'type': 'auto'}})
    assert info['kind'] == 'gitbash'
    assert info['family'] == 'bash'
    assert info['path'] == r'C:\Program Files\Git\bin\bash.exe'
    assert _detect_shell_type({'shell': {'type': 'auto'}}) == 'bash'


def test_windows_auto_detection_powershell_when_in_powershell(monkeypatch):
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('context._find_git_bash_path', lambda: r'C:\Program Files\Git\bin\bash.exe')
    monkeypatch.setattr('context._find_powershell_path', lambda: r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')
    monkeypatch.setattr('context._detect_running_parent_shell', lambda: 'powershell')
    monkeypatch.setenv('PSExecutionPolicyPreference', 'RemoteSigned')

    info = resolve_shell_environment({'shell': {'type': 'auto'}})
    assert info['kind'] == 'powershell'
    assert info['family'] == 'powershell'
    assert _detect_shell_type({'shell': {'type': 'auto'}}) == 'powershell'


def test_windows_explicit_powershell(monkeypatch):
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('context._find_powershell_path', lambda: r'C:\Program Files\PowerShell\7\pwsh.exe')

    info = resolve_shell_environment({'shell': {'type': 'powershell'}})
    assert info['kind'] == 'powershell'
    assert info['family'] == 'powershell'
    assert info['path'] == r'C:\Program Files\PowerShell\7\pwsh.exe'
    assert _detect_shell_type({'shell': {'type': 'powershell'}}) == 'powershell'


def test_win_to_posix_paths():
    assert _win_to_posix(r'C:\Users\foo\bar') == '/c/Users/foo/bar'
    assert _win_to_posix(r'D:\Projects\my-app') == '/d/Projects/my-app'
    assert _win_to_posix(r'C:\Users\foo\bar', wsl=True) == '/mnt/c/Users/foo/bar'


def test_platform_hints_match_resolved_shell(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Windows')
    monkeypatch.setattr('sys.platform', 'win32')
    monkeypatch.setattr('context._find_git_bash_path', lambda: r'C:\Program Files\Git\bin\bash.exe')
    monkeypatch.setattr('context._detect_running_parent_shell', lambda: None)

    hints = get_platform_hints({'shell': {'type': 'auto'}})
    assert 'Windows(gitbash/POSIX)' in hints
    assert 'cat,grep,ls,curl,&&' in hints
