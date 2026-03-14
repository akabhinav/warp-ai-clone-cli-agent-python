"""Tests for platform detection and cross-platform utilities."""

import os
import re
import pytest
from unittest.mock import patch

from pyoz.platform import (
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX,
    PLATFORM_NAME,
    HAS_POWERSHELL,
    POWERSHELL_COMMAND_MAP,
    get_shell_info,
    get_powershell_equivalent,
    get_command_reference,
    normalize_path,
    to_posix_path,
    get_home_dir,
    get_temp_dir,
    build_shell_command,
    get_env_var_syntax,
    get_path_separator,
    get_blocked_patterns,
)


class TestPlatformDetection:
    def test_platform_name_valid(self):
        assert PLATFORM_NAME in ("windows", "macos", "linux")

    def test_exactly_one_platform(self):
        # On any system, exactly one should be True
        count = sum([IS_WINDOWS, IS_MACOS, IS_LINUX])
        assert count == 1

    def test_platform_matches_os_name(self):
        if os.name == "nt":
            assert IS_WINDOWS
        else:
            assert not IS_WINDOWS


class TestShellInfo:
    def test_get_shell_info_returns_dict(self):
        info = get_shell_info()
        assert "shell" in info
        assert "name" in info
        assert "path" in info
        assert "platform" in info

    def test_shell_info_platform_matches(self):
        info = get_shell_info()
        assert info["platform"] == PLATFORM_NAME


class TestPowerShellCommandMap:
    def test_has_essential_mappings(self):
        essential = ["ls", "cat", "grep", "find", "cp", "mv", "rm", "mkdir", "pwd", "cd"]
        for cmd in essential:
            assert cmd in POWERSHELL_COMMAND_MAP, f"Missing PowerShell mapping for: {cmd}"

    def test_get_powershell_equivalent(self):
        result = get_powershell_equivalent("ls")
        assert result == "Get-ChildItem"

    def test_get_powershell_equivalent_grep(self):
        result = get_powershell_equivalent("grep")
        assert result == "Select-String"

    def test_get_powershell_equivalent_cat(self):
        result = get_powershell_equivalent("cat")
        assert result == "Get-Content"

    def test_get_powershell_equivalent_unknown(self):
        result = get_powershell_equivalent("nonexistent_command")
        assert result is None

    def test_get_command_reference(self):
        ref = get_command_reference()
        assert "PowerShell" in ref
        assert "Get-ChildItem" in ref
        assert "Select-String" in ref

    def test_map_covers_navigation(self):
        nav_cmds = ["pwd", "cd", "ls", "find"]
        for cmd in nav_cmds:
            assert cmd in POWERSHELL_COMMAND_MAP

    def test_map_covers_network(self):
        net_cmds = ["curl", "wget", "ping"]
        for cmd in net_cmds:
            assert cmd in POWERSHELL_COMMAND_MAP

    def test_map_covers_system(self):
        sys_cmds = ["ps", "kill", "which", "whoami"]
        for cmd in sys_cmds:
            assert cmd in POWERSHELL_COMMAND_MAP


class TestPathUtilities:
    def test_normalize_path(self):
        result = normalize_path("/some/path/to/file")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_to_posix_path(self):
        result = to_posix_path("C:\\Users\\name\\project")
        assert "\\" not in result
        assert "C:/Users/name/project" == result

    def test_to_posix_path_already_posix(self):
        result = to_posix_path("/home/user/project")
        assert result == "/home/user/project"

    def test_get_home_dir(self):
        home = get_home_dir()
        assert os.path.isdir(home)

    def test_get_temp_dir(self):
        tmp = get_temp_dir()
        assert os.path.isdir(tmp)


class TestShellCommand:
    def test_build_shell_command_unix(self):
        if not IS_WINDOWS:
            result = build_shell_command("echo hello")
            assert result == "echo hello"

    def test_get_env_var_syntax(self):
        result = get_env_var_syntax("MY_VAR", "my_value")
        assert "MY_VAR" in result
        assert "my_value" in result
        if IS_WINDOWS and HAS_POWERSHELL:
            assert "$env:" in result
        elif IS_WINDOWS:
            assert "set " in result
        else:
            assert "export " in result

    def test_get_path_separator(self):
        sep = get_path_separator()
        if IS_WINDOWS:
            assert sep == ";"
        else:
            assert sep == ":"


class TestBlockedPatterns:
    def test_get_blocked_patterns_returns_list(self):
        patterns = get_blocked_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0

    def test_blocked_patterns_are_valid_regex(self):
        patterns = get_blocked_patterns()
        for p in patterns:
            # Should not raise
            re.compile(p, re.IGNORECASE)

    def test_common_patterns_always_present(self):
        patterns = get_blocked_patterns()
        pattern_str = " ".join(patterns)
        assert "format" in pattern_str.lower()

    def test_unix_patterns_on_unix(self):
        if not IS_WINDOWS:
            patterns = get_blocked_patterns()
            pattern_str = " ".join(patterns)
            assert "rm" in pattern_str
            assert "mkfs" in pattern_str

    def test_windows_patterns_on_windows(self):
        if IS_WINDOWS:
            patterns = get_blocked_patterns()
            pattern_str = " ".join(patterns)
            assert "Remove-Item" in pattern_str or "Format-Volume" in pattern_str


class TestCommandToolsIntegration:
    def test_run_command_echo(self):
        from pyoz.tools.command_tools import run_command
        result = run_command("echo hello")
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_run_command_blocked(self):
        from pyoz.tools.command_tools import run_command
        with pytest.raises(PermissionError):
            run_command("rm -rf /")

    def test_get_platform_command_on_unix(self):
        from pyoz.tools.command_tools import get_platform_command
        if not IS_WINDOWS:
            assert get_platform_command("ls -la") == "ls -la"

    def test_get_platform_command_mapping(self):
        from pyoz.tools.command_tools import get_platform_command
        if IS_WINDOWS:
            result = get_platform_command("ls")
            assert "Get-ChildItem" in result


class TestContextToolsPlatform:
    def test_platform_info(self):
        from pyoz.tools.context_tools import platform_info
        result = platform_info()
        assert "Platform:" in result
        assert "Shell:" in result

    def test_platform_info_has_shell_name(self):
        from pyoz.tools.context_tools import platform_info
        result = platform_info()
        info = get_shell_info()
        assert info["name"] in result


class TestRegistryPlatformAware:
    def test_tool_count_with_platform_info(self):
        from pyoz.tools.registry import get_tool_definitions_claude, get_tool_definitions_openai
        # Now 14 tools (13 original + platform_info)
        assert len(get_tool_definitions_claude()) == 24
        assert len(get_tool_definitions_openai()) == 24

    def test_run_command_description_exists(self):
        from pyoz.tools.registry import get_tool_definitions_claude
        tools = get_tool_definitions_claude()
        run_cmd = [t for t in tools if t["name"] == "run_command"][0]
        assert "command" in run_cmd["description"].lower()

    def test_platform_info_tool_exists(self):
        from pyoz.tools.registry import get_tool_definitions_claude
        tools = get_tool_definitions_claude()
        names = [t["name"] for t in tools]
        assert "platform_info" in names
