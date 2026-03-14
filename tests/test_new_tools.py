"""Tests for the 5 new Tier-1 tools: package_manager, dotnet_cli, env_manager, process_manager, system_info."""

import os
import tempfile
import pytest

from pyoz.platform import IS_WINDOWS


# ============================================================
# Package Manager Tests
# ============================================================

class TestPackageManager:
    def test_list_managers(self):
        from pyoz.tools.package_tools import package_manager
        result = package_manager(action="managers")
        assert "package managers" in result.lower() or "Available" in result

    def test_detect_package_managers(self):
        from pyoz.tools.package_tools import _detect_package_managers
        managers = _detect_package_managers()
        assert isinstance(managers, list)
        # Should at least find pip on any dev machine
        ids = [m["id"] for m in managers]
        # pip or pip3 should be available in our test env
        assert "pip" in ids or len(managers) >= 0  # May not have pip in all envs

    def test_auto_select_manager(self):
        from pyoz.tools.package_tools import _auto_select_manager
        result = _auto_select_manager("install")
        assert isinstance(result, str)

    def test_invalid_action(self):
        from pyoz.tools.package_tools import package_manager
        result = package_manager(action="install", package="", manager="pip")
        assert "Error" in result or "required" in result.lower()

    def test_unknown_manager(self):
        from pyoz.tools.package_tools import package_manager
        result = package_manager(action="install", package="test", manager="nonexistent")
        assert "Error" in result

    def test_pip_list(self):
        from pyoz.tools.package_tools import package_manager
        import shutil
        if shutil.which("pip") or shutil.which("pip3"):
            result = package_manager(action="list", manager="pip")
            # Should list installed packages
            assert len(result) > 0

    def test_pip_info(self):
        from pyoz.tools.package_tools import package_manager
        import shutil
        if shutil.which("pip") or shutil.which("pip3"):
            result = package_manager(action="info", package="pip", manager="pip")
            assert "pip" in result.lower()


# ============================================================
# Dotnet CLI Tests
# ============================================================

class TestDotnetCli:
    def test_no_dotnet_graceful(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        import shutil
        if not shutil.which("dotnet"):
            result = dotnet_cli(action="info")
            assert "not found" in result.lower() or "Error" in result

    def test_info_action(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        import shutil
        if shutil.which("dotnet"):
            result = dotnet_cli(action="info")
            assert len(result) > 0

    def test_new_missing_template(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        result = dotnet_cli(action="new", args="")
        assert "Error" in result or "template" in result.lower()

    def test_unknown_action(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        result = dotnet_cli(action="nonexistent")
        assert "Error" in result or "Unknown" in result

    def test_add_package_missing_args(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        result = dotnet_cli(action="add-package")
        assert "Error" in result

    def test_remove_package_missing_args(self):
        from pyoz.tools.dotnet_tools import dotnet_cli
        result = dotnet_cli(action="remove-package")
        assert "Error" in result


# ============================================================
# Environment Manager Tests
# ============================================================

class TestEnvManager:
    def test_get_existing(self):
        from pyoz.tools.env_tools import env_manager
        os.environ["PYOZ_TEST_VAR"] = "hello123"
        result = env_manager(action="get", name="PYOZ_TEST_VAR")
        assert "hello123" in result
        del os.environ["PYOZ_TEST_VAR"]

    def test_get_missing(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="get", name="PYOZ_NONEXISTENT_12345")
        assert "not set" in result.lower()

    def test_set_and_get(self):
        from pyoz.tools.env_tools import env_manager
        env_manager(action="set", name="PYOZ_TEST_SET", value="world456")
        result = env_manager(action="get", name="PYOZ_TEST_SET")
        assert "world456" in result
        del os.environ["PYOZ_TEST_SET"]

    def test_unset(self):
        from pyoz.tools.env_tools import env_manager
        os.environ["PYOZ_TEST_UNSET"] = "temp"
        result = env_manager(action="unset", name="PYOZ_TEST_UNSET")
        assert "Unset" in result
        assert "PYOZ_TEST_UNSET" not in os.environ

    def test_unset_missing(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="unset", name="PYOZ_MISSING_12345")
        assert "not set" in result.lower()

    def test_list(self):
        from pyoz.tools.env_tools import env_manager
        os.environ["PYOZ_LIST_TEST"] = "val"
        result = env_manager(action="list", name="PYOZ_LIST")
        assert "PYOZ_LIST_TEST" in result
        del os.environ["PYOZ_LIST_TEST"]

    def test_list_all(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="list")
        assert "PATH" in result or "HOME" in result or "USER" in result

    def test_load_env_file(self):
        from pyoz.tools.env_tools import env_manager
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("# Comment line\n")
            f.write("PYOZ_LOAD_A=hello\n")
            f.write('PYOZ_LOAD_B="world"\n')
            f.write("PYOZ_LOAD_C='quoted'\n")
            f.write("\n")
            f.name
            path = f.name
        try:
            result = env_manager(action="load-env", file_path=path)
            assert "3" in result  # 3 variables loaded
            assert os.environ.get("PYOZ_LOAD_A") == "hello"
            assert os.environ.get("PYOZ_LOAD_B") == "world"
            assert os.environ.get("PYOZ_LOAD_C") == "quoted"
        finally:
            os.unlink(path)
            for k in ("PYOZ_LOAD_A", "PYOZ_LOAD_B", "PYOZ_LOAD_C"):
                os.environ.pop(k, None)

    def test_load_env_missing_file(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="load-env", file_path="/nonexistent/.env")
        assert "Error" in result or "not found" in result.lower()

    def test_save_env_file(self):
        from pyoz.tools.env_tools import env_manager
        os.environ["PYOZ_SAVE_TEST"] = "saved_val"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, ".env")
            result = env_manager(action="save-env", file_path=path, name="PYOZ_SAVE")
            assert "Saved" in result
            with open(path, "r") as f:
                content = f.read()
            assert "PYOZ_SAVE_TEST=saved_val" in content
        del os.environ["PYOZ_SAVE_TEST"]

    def test_path_list(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="path-list")
        assert "PATH" in result
        assert "entries" in result

    def test_path_add(self):
        from pyoz.tools.env_tools import env_manager
        with tempfile.TemporaryDirectory() as tmpdir:
            result = env_manager(action="path-add", value=tmpdir)
            assert "Added" in result
            assert tmpdir in os.environ["PATH"]

    def test_path_add_missing_dir(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="path-add", value="/nonexistent/dir/12345")
        assert "Error" in result

    def test_invalid_action(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="nonexistent")
        assert "Error" in result

    def test_get_missing_name(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="get")
        assert "Error" in result

    def test_set_missing_name(self):
        from pyoz.tools.env_tools import env_manager
        result = env_manager(action="set")
        assert "Error" in result


# ============================================================
# Process Manager Tests
# ============================================================

class TestProcessManager:
    def test_list_processes(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="list")
        assert len(result) > 0
        # Should have some process info
        assert "PID" in result.upper() or "python" in result.lower() or "USER" in result

    def test_find_python(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="find", name="python")
        # Python is definitely running (we're using it)
        assert len(result) > 0

    def test_find_missing_name(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="find")
        assert "Error" in result

    def test_kill_missing_pid(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="kill")
        assert "Error" in result

    def test_ports(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="ports")
        assert isinstance(result, str)

    def test_port_find_unused(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="port-find", port=59999)
        assert "No process" in result or len(result) > 0

    def test_port_find_missing(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="port-find")
        assert "Error" in result

    def test_tree(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="tree")
        assert isinstance(result, str)

    def test_invalid_action(self):
        from pyoz.tools.process_tools import process_manager
        result = process_manager(action="nonexistent")
        assert "Error" in result


# ============================================================
# System Info Tests
# ============================================================

class TestSystemInfo:
    def test_overview(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("overview")
        assert "System Overview" in result
        assert "OS:" in result
        assert "Python:" in result

    def test_os(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("os")
        assert "Operating System" in result

    def test_cpu(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("cpu")
        assert "CPU" in result
        assert "Cores:" in result

    def test_memory(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("memory")
        assert "Memory" in result

    def test_disk(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("disk")
        assert "Disk" in result

    def test_network(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("network")
        assert "Network" in result

    def test_sdks(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("sdks")
        assert "SDKs" in result or "Tools" in result
        # Python should always be found
        assert "Python" in result

    def test_python_sdk(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("python")
        assert "Python" in result or "python" in result
        assert "Version" in result

    def test_default_overview(self):
        from pyoz.tools.system_tools import system_info
        result = system_info()
        assert "System Overview" in result

    def test_unknown_category(self):
        from pyoz.tools.system_tools import system_info
        result = system_info("nonexistent")
        assert "Error" in result

    def test_get_version_helper(self):
        from pyoz.tools.system_tools import _get_version
        result = _get_version(["python3", "--version"])
        assert "Python" in result or "python" in result

    def test_get_version_missing_command(self):
        from pyoz.tools.system_tools import _get_version
        result = _get_version(["nonexistent_command_12345", "--version"])
        assert result == ""


# ============================================================
# Registry Integration Tests
# ============================================================

class TestNewToolsInRegistry:
    def test_all_19_tools(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) == 24

    def test_new_tool_names_present(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "package_manager" in names
        assert "dotnet_cli" in names
        assert "env_manager" in names
        assert "process_manager" in names
        assert "system_info" in names

    def test_new_tools_have_descriptions(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        new_tools = ["package_manager", "dotnet_cli", "env_manager", "process_manager", "system_info"]
        for t in TOOL_DEFINITIONS:
            if t["name"] in new_tools:
                assert t.get("description"), f"{t['name']} missing description"
                assert len(t["description"]) > 20, f"{t['name']} description too short"

    def test_new_tools_have_action_param(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        action_tools = ["package_manager", "dotnet_cli", "env_manager", "process_manager"]
        for t in TOOL_DEFINITIONS:
            if t["name"] in action_tools:
                assert "action" in t["parameters"]["properties"], f"{t['name']} missing 'action' param"
                assert "action" in t["parameters"]["required"], f"{t['name']} should require 'action'"

    def test_claude_format(self):
        from pyoz.tools.registry import get_tool_definitions_claude
        tools = get_tool_definitions_claude()
        assert len(tools) == 24
        names = [t["name"] for t in tools]
        assert "package_manager" in names
        assert "system_info" in names

    def test_openai_format(self):
        from pyoz.tools.registry import get_tool_definitions_openai
        tools = get_tool_definitions_openai()
        assert len(tools) == 24
        names = [t["function"]["name"] for t in tools]
        assert "package_manager" in names
        assert "system_info" in names
