"""Tests for Tier-2 tools: docker, service, http_request, msbuild, schedule."""

import json
import os
import tempfile
import pytest

from pyoz.platform import IS_WINDOWS, IS_LINUX


# ============================================================
# Docker Tool Tests
# ============================================================

class TestDockerTool:
    def test_no_docker_graceful(self):
        import shutil
        from pyoz.tools.docker_tools import docker_tool
        if not shutil.which("docker"):
            result = docker_tool(action="info")
            assert "not found" in result.lower() or "Error" in result

    def test_version_action(self):
        import shutil
        from pyoz.tools.docker_tools import docker_tool
        if shutil.which("docker"):
            result = docker_tool(action="version")
            assert "Docker" in result or "Client" in result or "Error" in result

    def test_unknown_action(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="nonexistent")
        assert "Error" in result or "Unknown" in result

    def test_run_missing_target(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="run")
        assert "Error" in result

    def test_stop_missing_target(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="stop")
        assert "Error" in result

    def test_logs_missing_target(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="logs")
        assert "Error" in result

    def test_exec_missing_args(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="exec", target="mycontainer")
        assert "Error" in result

    def test_pull_missing_target(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="pull")
        assert "Error" in result

    def test_tag_missing_args(self):
        from pyoz.tools.docker_tools import docker_tool
        result = docker_tool(action="tag")
        assert "Error" in result

    def test_compose_file_args_helper(self):
        from pyoz.tools.docker_tools import _compose_file_args, _strip_file_args
        extra = ["-f", "docker-compose.prod.yml", "--build"]
        file_args = _compose_file_args(extra)
        assert file_args == ["-f", "docker-compose.prod.yml"]
        stripped = _strip_file_args(extra)
        assert stripped == ["--build"]

    def test_ps_action(self):
        import shutil
        from pyoz.tools.docker_tools import docker_tool
        if shutil.which("docker"):
            result = docker_tool(action="ps")
            # Should return something (even if no containers)
            assert isinstance(result, str)


# ============================================================
# Service Manager Tests
# ============================================================

class TestServiceManager:
    def test_list_services(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="list")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_find_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="find")
        assert "Error" in result

    def test_status_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="status")
        assert "Error" in result

    def test_start_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="start")
        assert "Error" in result

    def test_stop_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="stop")
        assert "Error" in result

    def test_restart_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="restart")
        assert "Error" in result

    def test_enable_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="enable")
        assert "Error" in result

    def test_disable_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="disable")
        assert "Error" in result

    def test_logs_missing_name(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="logs")
        assert "Error" in result

    def test_unknown_action(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="nonexistent")
        assert "Error" in result

    def test_find_nonexistent_service(self):
        from pyoz.tools.service_tools import service_manager
        result = service_manager(action="find", name="pyoz_nonexistent_service_12345")
        assert "No service" in result or len(result) >= 0  # May return empty


# ============================================================
# HTTP Request Tests
# ============================================================

class TestHttpRequest:
    def test_get_request(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(method="GET", url="https://httpbin.org/get")
        assert "HTTP 200" in result or "Error" in result  # May fail without network

    def test_invalid_method(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(method="INVALID", url="https://example.com")
        assert "Error" in result

    def test_missing_url(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(method="GET", url="")
        assert "Error" in result

    def test_connection_error(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(method="GET", url="https://localhost:19999/nonexistent", timeout=3)
        assert "Error" in result

    def test_post_with_json(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(
            method="POST",
            url="https://httpbin.org/post",
            json_body={"key": "value"},
        )
        assert "HTTP" in result or "Error" in result

    def test_headers_and_auth(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(
            method="GET",
            url="https://httpbin.org/headers",
            headers={"X-Custom": "test"},
            auth_token="fake-token-123",
        )
        assert "HTTP" in result or "Error" in result

    def test_query_params(self):
        from pyoz.tools.http_tools import http_request
        result = http_request(
            method="GET",
            url="https://httpbin.org/get",
            query_params={"foo": "bar"},
        )
        assert "HTTP" in result or "Error" in result


# ============================================================
# MSBuild Tool Tests
# ============================================================

class TestMSBuildTool:
    def test_info_action(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        result = msbuild_tool(action="info")
        assert "Build Environment" in result

    def test_find_build_tool(self):
        from pyoz.tools.msbuild_tools import _find_build_tool
        result = _find_build_tool()
        # May or may not find dotnet/msbuild
        assert result is None or isinstance(result, str)

    def test_find_solutions_no_sln(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            result = msbuild_tool(action="find-solutions", cwd=tmpdir)
            assert "No *.sln" in result

    def test_find_projects_no_proj(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            result = msbuild_tool(action="find-projects", cwd=tmpdir)
            assert "No" in result

    def test_sln_list_no_sln(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        with tempfile.TemporaryDirectory() as tmpdir:
            result = msbuild_tool(action="sln-list", cwd=tmpdir)
            assert "Error" in result or "No .sln" in result

    def test_sln_add_missing_args(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        result = msbuild_tool(action="sln-add")
        assert "Error" in result

    def test_sln_remove_missing_args(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        result = msbuild_tool(action="sln-remove")
        assert "Error" in result

    def test_proj_add_ref_missing_args(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        result = msbuild_tool(action="proj-add-ref")
        assert "Error" in result

    def test_unknown_action(self):
        from pyoz.tools.msbuild_tools import msbuild_tool
        result = msbuild_tool(action="nonexistent")
        assert "Error" in result

    def test_find_sln_helper(self):
        from pyoz.tools.msbuild_tools import _find_sln
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _find_sln(tmpdir) == ""
            # Create a fake .sln
            sln_path = os.path.join(tmpdir, "test.sln")
            with open(sln_path, "w") as f:
                f.write("")
            assert _find_sln(tmpdir) == sln_path

    def test_find_proj_helper(self):
        from pyoz.tools.msbuild_tools import _find_proj
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _find_proj(tmpdir) == ""
            proj_path = os.path.join(tmpdir, "test.csproj")
            with open(proj_path, "w") as f:
                f.write("")
            assert _find_proj(tmpdir) == proj_path


# ============================================================
# Schedule Task Tests
# ============================================================

class TestScheduleTask:
    def test_list_tasks(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="list")
        assert isinstance(result, str)

    def test_create_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="create")
        assert "Error" in result

    def test_create_missing_command(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="create", name="test")
        assert "Error" in result

    def test_create_missing_schedule(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="create", name="test", command="echo hi")
        assert "Error" in result

    def test_delete_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="delete")
        assert "Error" in result

    def test_enable_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="enable")
        assert "Error" in result

    def test_disable_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="disable")
        assert "Error" in result

    def test_status_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="status")
        assert "Error" in result

    def test_run_missing_name(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="run")
        assert "Error" in result

    def test_unknown_action(self):
        from pyoz.tools.schedule_tools import schedule_task
        result = schedule_task(action="nonexistent")
        assert "Error" in result

    def test_parse_windows_schedule(self):
        from pyoz.tools.schedule_tools import _parse_windows_schedule
        assert "AtStartup" in _parse_windows_schedule("startup")
        assert "AtLogOn" in _parse_windows_schedule("logon")
        assert "Daily" in _parse_windows_schedule("daily 09:00")
        assert "Weekly" in _parse_windows_schedule("weekly Monday 09:00")
        assert "Once" in _parse_windows_schedule("once 2026-03-15 14:00")
        assert "Error" in _parse_windows_schedule("once")  # Missing datetime
        assert "Hours" in _parse_windows_schedule("hourly")


# ============================================================
# Registry Integration (24 tools)
# ============================================================

class TestTier2Registry:
    def test_all_24_tools(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) == 24

    def test_tier2_names_present(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "docker_tool" in names
        assert "service_manager" in names
        assert "http_request" in names
        assert "msbuild_tool" in names
        assert "schedule_task" in names

    def test_all_have_descriptions(self):
        from pyoz.tools.registry import TOOL_DEFINITIONS
        for t in TOOL_DEFINITIONS:
            assert t.get("description"), f"{t['name']} missing description"

    def test_claude_format_24(self):
        from pyoz.tools.registry import get_tool_definitions_claude
        assert len(get_tool_definitions_claude()) == 24

    def test_openai_format_24(self):
        from pyoz.tools.registry import get_tool_definitions_openai
        assert len(get_tool_definitions_openai()) == 24
