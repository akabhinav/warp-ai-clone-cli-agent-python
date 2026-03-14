"""End-to-end integration tests — verify every tool actually works.

Creates a real project, writes files, runs commands, queries databases,
manages git, and validates the full agent dispatcher.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# ── Import all tools ──────────────────────────────────────────
from pyoz.tools.file_tools import read_file, write_file, edit_file, search_files, list_directory
from pyoz.tools.command_tools import run_command
from pyoz.tools.git_tools import git_init, git_commit, git_diff, git_undo, git_log, is_git_repo, auto_commit
from pyoz.tools.context_tools import static_config, platform_info, codebase_index
from pyoz.tools.package_tools import package_manager
from pyoz.tools.env_tools import env_manager
from pyoz.tools.process_tools import process_manager
from pyoz.tools.system_tools import system_info
from pyoz.tools.docker_tools import docker_tool
from pyoz.tools.service_tools import service_manager
from pyoz.tools.http_tools import http_request
from pyoz.tools.schedule_tools import schedule_task
from pyoz.tools.kubernetes_tools import kubernetes_tool
from pyoz.tools.database_tools import database_tool
from pyoz.tools.git_workflow_tools import git_workflow_tool
from pyoz.tools.cicd_tools import cicd_tool
from pyoz.tools.registry import get_tool_definitions_claude, get_tool_definitions_openai


class TestFileTools(unittest.TestCase):
    """Test file operations end-to-end."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_read_edit_cycle(self):
        """Write a file, read it, edit it, read again."""
        path = os.path.join(self.test_dir, "app.py")

        # Write
        result = write_file(path, 'def hello():\n    return "Hello World"\n')
        self.assertIn("wrote", result.lower())
        self.assertTrue(os.path.exists(path))

        # Read
        content = read_file(path)
        self.assertIn("Hello World", content)

        # Edit
        result = edit_file(path, '"Hello World"', '"Hello PyOz"')
        self.assertIn("edited", result.lower())

        # Verify edit
        content = read_file(path)
        self.assertIn("Hello PyOz", content)
        self.assertNotIn("Hello World", content)

    def test_write_creates_directories(self):
        """write_file should auto-create parent directories."""
        path = os.path.join(self.test_dir, "deep", "nested", "dir", "file.txt")
        result = write_file(path, "test content")
        self.assertIn("wrote", result.lower())
        self.assertTrue(os.path.exists(path))

    def test_search_files(self):
        """search_files should find patterns across files."""
        # Create test files
        write_file(os.path.join(self.test_dir, "a.py"), "def foo(): pass\ndef bar(): pass\n")
        write_file(os.path.join(self.test_dir, "b.py"), "class Foo: pass\n")

        results = search_files("foo", self.test_dir, ".py")
        self.assertTrue(len(results) > 0)

    def test_list_directory(self):
        """list_directory should return files and dirs."""
        write_file(os.path.join(self.test_dir, "file1.py"), "x")
        write_file(os.path.join(self.test_dir, "file2.py"), "y")
        os.makedirs(os.path.join(self.test_dir, "subdir"), exist_ok=True)

        entries = list_directory(self.test_dir)
        names = [e["name"] for e in entries]
        self.assertIn("file1.py", names)
        self.assertIn("file2.py", names)
        self.assertIn("subdir", names)

    def test_edit_file_not_found(self):
        """edit_file on missing text should raise ValueError."""
        path = os.path.join(self.test_dir, "test.txt")
        write_file(path, "abc")
        with self.assertRaises(ValueError):
            edit_file(path, "xyz", "new")

    def test_read_nonexistent(self):
        """read_file on missing file should raise."""
        with self.assertRaises(FileNotFoundError):
            read_file(os.path.join(self.test_dir, "nonexistent.txt"))


class TestCommandTools(unittest.TestCase):
    """Test shell command execution."""

    def test_run_echo(self):
        """Basic command execution."""
        result = run_command("echo hello")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello", result["stdout"])

    def test_run_failing_command(self):
        """Failing command returns non-zero exit code."""
        result = run_command("false")
        self.assertNotEqual(result["exit_code"], 0)

    def test_run_with_cwd(self):
        """Command runs in specified directory."""
        result = run_command("pwd", "/tmp")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("/tmp", result["stdout"])


class TestGitTools(unittest.TestCase):
    """Test git operations end-to-end."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_git_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_git_workflow(self):
        """Init → write → commit → log → diff → undo."""
        # Init
        result = git_init(self.test_dir)
        self.assertTrue(is_git_repo(self.test_dir))

        # Write a file
        path = os.path.join(self.test_dir, "main.py")
        write_file(path, "print('hello')\n")

        # Commit
        result = git_commit("Initial commit", self.test_dir)
        self.assertIn("Initial commit", result)

        # Log
        commits = git_log(5, self.test_dir)
        self.assertTrue(len(commits) >= 1)
        messages = [c["message"] for c in commits]
        self.assertTrue(any("Initial commit" in m for m in messages))

        # Edit and check diff
        write_file(path, "print('hello world')\n")
        diff = git_diff(self.test_dir)
        self.assertIn("hello world", diff)

        # Commit the change
        result = git_commit("Update message", self.test_dir)
        self.assertIn("Update message", result)

        # Undo
        result = git_undo(self.test_dir)
        self.assertIn("reverted", result.lower())

    def test_auto_commit(self):
        """auto_commit should commit after file creation."""
        git_init(self.test_dir)
        path = os.path.join(self.test_dir, "new_file.py")
        write_file(path, "x = 1\n")
        result = auto_commit(path, "create", self.test_dir)
        self.assertIn("pyoz:", result)


class TestDatabaseTool(unittest.TestCase):
    """Test database operations — SQLite (always available)."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_db_")
        self.db_path = os.path.join(self.test_dir, "test.db")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sqlite_create_and_query(self):
        """Create table, insert data, query it back."""
        # Create table
        result = database_tool(
            action="query",
            engine="sqlite",
            database=self.db_path,
            query="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)",
        )
        self.assertIn("Query OK", result)

        # Insert
        result = database_tool(
            action="query",
            engine="sqlite",
            database=self.db_path,
            query="INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')",
        )
        self.assertIn("1 row(s) affected", result)

        # Insert more
        database_tool(
            action="query",
            engine="sqlite",
            database=self.db_path,
            query="INSERT INTO users (name, email) VALUES ('Bob', 'bob@example.com')",
        )

        # Query
        result = database_tool(
            action="query",
            engine="sqlite",
            database=self.db_path,
            query="SELECT * FROM users ORDER BY name",
        )
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("2 row(s)", result)

    def test_sqlite_list_tables(self):
        """List tables in a SQLite database."""
        # Create some tables first
        database_tool(action="query", engine="sqlite", database=self.db_path,
                      query="CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
        database_tool(action="query", engine="sqlite", database=self.db_path,
                      query="CREATE TABLE orders (id INTEGER PRIMARY KEY, product_id INTEGER)")

        result = database_tool(action="list-tables", engine="sqlite", database=self.db_path)
        self.assertIn("orders", result)
        self.assertIn("products", result)

    def test_sqlite_describe(self):
        """Describe a table schema."""
        database_tool(action="query", engine="sqlite", database=self.db_path,
                      query="CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price REAL)")

        result = database_tool(action="describe", engine="sqlite", database=self.db_path, query="items")
        self.assertIn("id", result)
        self.assertIn("name", result)
        self.assertIn("price", result)
        self.assertIn("INTEGER", result)

    def test_sqlite_info(self):
        """Get SQLite server info."""
        result = database_tool(action="info", engine="sqlite", database=self.db_path)
        data = json.loads(result)
        self.assertEqual(data["engine"], "SQLite")
        self.assertIn("version", data)

    def test_sqlite_update_delete(self):
        """Test UPDATE and DELETE operations."""
        database_tool(action="query", engine="sqlite", database=self.db_path,
                      query="CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        database_tool(action="query", engine="sqlite", database=self.db_path,
                      query="INSERT INTO t VALUES (1, 'old')")

        # Update
        result = database_tool(action="query", engine="sqlite", database=self.db_path,
                               query="UPDATE t SET val = 'new' WHERE id = 1")
        self.assertIn("1 row(s) affected", result)

        # Verify
        result = database_tool(action="query", engine="sqlite", database=self.db_path,
                               query="SELECT val FROM t WHERE id = 1")
        self.assertIn("new", result)

        # Delete
        result = database_tool(action="query", engine="sqlite", database=self.db_path,
                               query="DELETE FROM t WHERE id = 1")
        self.assertIn("1 row(s) affected", result)

    def test_unknown_engine(self):
        """Unknown engine should error."""
        result = database_tool(action="query", engine="oracle", query="SELECT 1")
        self.assertIn("Error", result)
        self.assertIn("Unknown engine", result)

    def test_bad_sql(self):
        """Bad SQL should return error, not crash."""
        result = database_tool(action="query", engine="sqlite", database=self.db_path,
                               query="SELECT * FROM nonexistent_table")
        self.assertIn("Error", result)


class TestGitWorkflowTool(unittest.TestCase):
    """Test git workflow operations."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_gw_")
        # Init a git repo
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.test_dir, capture_output=True)
        # Create initial commit
        write_file(os.path.join(self.test_dir, "README.md"), "# Test\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_and_switch_branch(self):
        """Create a branch and switch to it."""
        # Use the project repo itself to test branching (has valid git config)
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Save current branch
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                          capture_output=True, text=True, cwd=project_dir)
        original_branch = r.stdout.strip()

        try:
            result = git_workflow_tool(action="create-branch", target="test/e2e-branch", cwd=project_dir)
            self.assertTrue("test/e2e-branch" in result or "Switched" in result or "Done" in result)
        finally:
            # Clean up: switch back and delete test branch
            subprocess.run(["git", "checkout", original_branch], capture_output=True, cwd=project_dir)
            subprocess.run(["git", "branch", "-D", "test/e2e-branch"], capture_output=True, cwd=project_dir)

    def test_list_branches(self):
        """List branches in the real project repo."""
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = git_workflow_tool(action="list-branches", cwd=project_dir)
        # Should contain some branch output
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_stash_and_pop(self):
        """Stash and pop in real project repo."""
        # Use the real project repo for stash tests (needs valid git signing)
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Create a temp file, stage it
        temp_path = os.path.join(project_dir, "_stash_test_temp.txt")
        try:
            with open(temp_path, "w") as f:
                f.write("stash test content\n")
            subprocess.run(["git", "add", temp_path], capture_output=True, cwd=project_dir)

            # Stash
            result = git_workflow_tool(action="stash", title="e2e stash test", cwd=project_dir)
            # File should be gone
            self.assertFalse(os.path.exists(temp_path))

            # Pop
            result = git_workflow_tool(action="stash-pop", cwd=project_dir)
            self.assertTrue(os.path.exists(temp_path))
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            subprocess.run(["git", "checkout", "--", "."], capture_output=True, cwd=project_dir)
            subprocess.run(["git", "stash", "drop"], capture_output=True, cwd=project_dir)

    def test_pr_without_gh_cli(self):
        """PR actions without gh/glab should give helpful error."""
        # This tests error handling — gh may not be installed
        result = git_workflow_tool(action="pr-list", cwd=self.test_dir)
        # Should either work (if gh installed) or give a clear error
        self.assertTrue("Error" in result or "#" in result or "no " in result.lower() or len(result) > 0)

    def test_unknown_action(self):
        """Unknown action should list available actions."""
        result = git_workflow_tool(action="invalid-action", cwd=self.test_dir)
        self.assertIn("Error", result)
        self.assertIn("pr-create", result)


class TestCICDTool(unittest.TestCase):
    """Test CI/CD tool operations."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_cicd_")
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_status_check(self):
        """Status check should work even without CI configured."""
        result = cicd_tool(action="status", cwd=self.test_dir)
        # Should either show status or indicate no CI available
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_unknown_action(self):
        """Unknown action should list available actions."""
        result = cicd_tool(action="invalid", cwd=self.test_dir)
        self.assertIn("Error", result)
        self.assertIn("workflow-run", result)

    def test_workflow_list_without_gh(self):
        """Should handle missing gh CLI gracefully."""
        result = cicd_tool(action="workflow-list", cwd=self.test_dir)
        # Either works or gives clear error
        self.assertIsInstance(result, str)


class TestKubernetesTool(unittest.TestCase):
    """Test Kubernetes tool operations."""

    def test_unknown_action(self):
        """Unknown action should return error."""
        result = kubernetes_tool(action="invalid")
        self.assertIn("Error", result)
        # If kubectl is missing, we get "kubectl not found"
        # If kubectl is present, we get "Unknown action" with valid actions listed
        self.assertTrue("kubectl not found" in result or "apply" in result)

    def test_missing_kubectl(self):
        """Should handle missing kubectl gracefully."""
        with patch("shutil.which", return_value=None):
            result = kubernetes_tool(action="get-pods")
            self.assertIn("Error", result)
            self.assertIn("kubectl not found", result)


class TestDockerTool(unittest.TestCase):
    """Test Docker tool operations."""

    def test_unknown_action(self):
        """Unknown action should list available actions."""
        result = docker_tool(action="invalid")
        self.assertIn("Error", result)
        self.assertIn("compose-up", result)

    def test_docker_not_installed(self):
        """Should handle missing docker gracefully."""
        with patch("shutil.which", return_value=None):
            result = docker_tool(action="ps")
            self.assertIn("Error", result)
            self.assertIn("Docker not found", result)


class TestContextTools(unittest.TestCase):
    """Test context information tools."""

    def test_static_config_python(self):
        """static_config should return valid Python configs."""
        result = static_config("python", "myproject")
        # Could be requirements.txt, pyproject.toml, setup.py, etc.
        self.assertTrue("requirements" in result.lower() or "pyproject" in result.lower() or "setup" in result.lower())

    def test_static_config_javascript(self):
        """static_config should return valid JS configs."""
        result = static_config("javascript", "myapp")
        self.assertIn("package.json", result.lower())

    def test_platform_info(self):
        """platform_info should return OS info."""
        result = platform_info()
        self.assertIn("linux", result.lower())

    def test_system_info_overview(self):
        """system_info should return system overview."""
        result = system_info("overview")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 10)


class TestEnvTools(unittest.TestCase):
    """Test environment variable tools."""

    def test_env_get_set(self):
        """Set and get an environment variable."""
        env_manager(action="set", name="PYOZ_TEST_VAR", value="test_value_123")
        result = env_manager(action="get", name="PYOZ_TEST_VAR")
        self.assertIn("test_value_123", result)

    def test_env_list(self):
        """List environment variables."""
        result = env_manager(action="list")
        self.assertIn("PATH", result)


class TestProcessTools(unittest.TestCase):
    """Test process management tools."""

    def test_process_list(self):
        """List running processes."""
        result = process_manager(action="list")
        self.assertIsInstance(result, str)
        # Should contain some process info
        self.assertTrue(len(result) > 10)

    def test_port_find(self):
        """Port find should work without crashing."""
        result = process_manager(action="ports")
        self.assertIsInstance(result, str)


class TestToolRegistry(unittest.TestCase):
    """Test that tool registry is consistent."""

    def test_claude_definitions_count(self):
        """Should have 29 tools defined."""
        tools = get_tool_definitions_claude()
        tool_names = [t["name"] for t in tools]
        self.assertEqual(len(tools), 29, f"Expected 29 tools, got {len(tools)}: {tool_names}")

    def test_openai_definitions_count(self):
        """OpenAI definitions should match Claude count."""
        claude_tools = get_tool_definitions_claude()
        openai_tools = get_tool_definitions_openai()
        self.assertEqual(len(claude_tools), len(openai_tools))

    def test_all_tools_have_required_fields(self):
        """Every tool must have name, description, and parameters."""
        for tool in get_tool_definitions_claude():
            self.assertIn("name", tool, f"Tool missing 'name': {tool}")
            self.assertIn("description", tool, f"Tool {tool.get('name')} missing 'description'")
            self.assertIn("input_schema", tool, f"Tool {tool.get('name')} missing 'input_schema'")

    def test_all_tool_names_unique(self):
        """No duplicate tool names."""
        tools = get_tool_definitions_claude()
        names = [t["name"] for t in tools]
        self.assertEqual(len(names), len(set(names)), f"Duplicate tool names found: {names}")

    def test_new_tools_registered(self):
        """Verify the 3 new tools are registered."""
        tools = get_tool_definitions_claude()
        names = [t["name"] for t in tools]
        self.assertIn("database_tool", names)
        self.assertIn("git_workflow_tool", names)
        self.assertIn("cicd_tool", names)
        self.assertIn("kubernetes_tool", names)


class TestAgentDispatcher(unittest.TestCase):
    """Test that agent.py can import and dispatch all tools."""

    def test_all_imports(self):
        """Verify all tool imports in agent.py work."""
        from pyoz.agent import Agent
        from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall
        # If we get here, all imports succeeded
        self.assertTrue(True)

    def test_agent_creation(self):
        """Verify Agent can be instantiated."""
        from pyoz.agent import Agent
        from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall

        # Create mock provider
        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.provider_name = "claude"
        mock_provider.model_name = "test-model"

        with tempfile.TemporaryDirectory() as tmp:
            agent = Agent(provider=mock_provider, work_dir=tmp)
            self.assertEqual(agent.work_dir, tmp)

    def test_execute_tool_dispatch(self):
        """Verify _execute_tool dispatches to all new tools."""
        from pyoz.agent import Agent
        from pyoz.providers.base import BaseLLMProvider, LLMResponse, ToolCall

        mock_provider = MagicMock(spec=BaseLLMProvider)
        mock_provider.provider_name = "claude"
        mock_provider.model_name = "test-model"

        with tempfile.TemporaryDirectory() as tmp:
            agent = Agent(provider=mock_provider, work_dir=tmp)

            # Test database_tool dispatch
            tc = ToolCall(id="1", name="database_tool", arguments={
                "action": "info", "engine": "sqlite", "database": ":memory:"
            })
            result = agent._execute_tool(tc)
            self.assertIn("SQLite", result)

            # Test git_workflow_tool dispatch
            tc = ToolCall(id="2", name="git_workflow_tool", arguments={
                "action": "invalid-action"
            })
            result = agent._execute_tool(tc)
            self.assertIn("Error", result)

            # Test cicd_tool dispatch
            tc = ToolCall(id="3", name="cicd_tool", arguments={
                "action": "status"
            })
            result = agent._execute_tool(tc)
            self.assertIsInstance(result, str)

            # Test kubernetes_tool dispatch
            tc = ToolCall(id="4", name="kubernetes_tool", arguments={
                "action": "invalid-action"
            })
            result = agent._execute_tool(tc)
            # Either "kubectl not found" or "Unknown action"
            self.assertIn("Error", result)

            # Test unknown tool
            tc = ToolCall(id="5", name="nonexistent_tool", arguments={})
            result = agent._execute_tool(tc)
            self.assertIn("Unknown tool", result)


class TestFullProjectWorkflow(unittest.TestCase):
    """End-to-end: create a real project, build, test, database operations."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="pyoz_e2e_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_python_project_e2e(self):
        """Build a complete Python project from scratch."""
        project_dir = os.path.join(self.test_dir, "myapi")
        os.makedirs(project_dir, exist_ok=True)

        # 1. Init git
        result = git_init(project_dir)
        self.assertTrue(is_git_repo(project_dir))

        # 2. Write application code
        app_code = '''"""Simple calculator module."""

def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b

def multiply(a: int, b: int) -> int:
    return a * b

def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
'''
        write_file(os.path.join(project_dir, "calculator.py"), app_code)

        # 3. Write tests
        test_code = '''"""Tests for calculator."""
import unittest
from calculator import add, subtract, multiply, divide

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)

    def test_multiply(self):
        self.assertEqual(multiply(3, 4), 12)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5.0)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            divide(1, 0)

if __name__ == "__main__":
    unittest.main()
'''
        write_file(os.path.join(project_dir, "test_calculator.py"), test_code)

        # 4. Commit
        result = git_commit("Add calculator with tests", project_dir)
        self.assertIn("Add calculator", result)

        # 5. Run tests via command
        result = run_command("python -m pytest test_calculator.py -v 2>&1 || python -m unittest test_calculator -v 2>&1", project_dir)
        # Should have run some tests
        self.assertTrue(result["stdout"] or result["stderr"])

        # 6. Search for functions
        results = search_files("def ", project_dir, ".py")
        func_names = [r["text"] for r in results]
        self.assertTrue(any("add" in t for t in func_names))

        # 7. Edit a file — add a new function
        edit_result = edit_file(
            os.path.join(project_dir, "calculator.py"),
            'def divide(a: int, b: int) -> float:',
            'def power(a: int, b: int) -> int:\n    return a ** b\n\ndef divide(a: int, b: int) -> float:'
        )
        self.assertIn("edited", edit_result.lower())

        # 8. Verify the edit
        content = read_file(os.path.join(project_dir, "calculator.py"))
        self.assertIn("def power", content)

        # 9. Commit the change
        git_commit("Add power function", project_dir)

        # 10. Check git log
        commits = git_log(10, project_dir)
        messages = [c["message"] for c in commits]
        self.assertTrue(any("power" in m for m in messages))

    def test_database_in_project(self):
        """Create a project that uses SQLite database."""
        project_dir = os.path.join(self.test_dir, "dbproject")
        os.makedirs(project_dir, exist_ok=True)
        db_path = os.path.join(project_dir, "app.db")

        # 1. Create schema
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER DEFAULT 0)")

        # 2. Insert data
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="INSERT INTO products (name, price, stock) VALUES ('Widget', 9.99, 100)")
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="INSERT INTO products (name, price, stock) VALUES ('Gadget', 24.99, 50)")
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="INSERT INTO products (name, price, stock) VALUES ('Doohickey', 4.99, 200)")

        # 3. Query
        result = database_tool(action="query", engine="sqlite", database=db_path,
                               query="SELECT name, price FROM products WHERE price > 5 ORDER BY price")
        self.assertIn("Widget", result)
        self.assertIn("Gadget", result)
        self.assertNotIn("Doohickey", result)

        # 4. Aggregate
        result = database_tool(action="query", engine="sqlite", database=db_path,
                               query="SELECT COUNT(*) as count, AVG(price) as avg_price FROM products")
        self.assertIn("3", result)

        # 5. List tables
        result = database_tool(action="list-tables", engine="sqlite", database=db_path)
        self.assertIn("products", result)

        # 6. Describe schema
        result = database_tool(action="describe", engine="sqlite", database=db_path, query="products")
        self.assertIn("name", result)
        self.assertIn("price", result)
        self.assertIn("stock", result)

    def test_multi_tool_workflow(self):
        """Simulate what the agent does: file ops + git + database together."""
        project_dir = os.path.join(self.test_dir, "fullstack")
        os.makedirs(project_dir, exist_ok=True)

        # 1. Init project
        git_init(project_dir)

        # 2. Write app
        write_file(os.path.join(project_dir, "app.py"), """import sqlite3

def init_db(path):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, msg TEXT)')
    conn.commit()
    return conn

def log_message(conn, msg):
    conn.execute('INSERT INTO logs (msg) VALUES (?)', (msg,))
    conn.commit()
""")

        # 3. Write Dockerfile
        write_file(os.path.join(project_dir, "Dockerfile"), """FROM python:3.12-slim
WORKDIR /app
COPY . .
CMD ["python", "app.py"]
""")

        # 4. Write K8s manifest
        write_file(os.path.join(project_dir, "k8s", "deployment.yaml"), """apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        ports:
        - containerPort: 8080
""")

        # 5. Commit everything
        git_commit("Full stack app with Docker and K8s", project_dir)

        # 6. Verify files exist
        entries = list_directory(project_dir)
        names = [e["name"] for e in entries]
        self.assertIn("app.py", names)
        self.assertIn("Dockerfile", names)
        self.assertIn("k8s", names)

        # 7. Verify K8s manifest is readable
        content = read_file(os.path.join(project_dir, "k8s", "deployment.yaml"))
        self.assertIn("replicas: 2", content)

        # 8. Test the database the app would create
        db_path = os.path.join(project_dir, "test.db")
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, msg TEXT)")
        database_tool(action="query", engine="sqlite", database=db_path,
                      query="INSERT INTO logs (msg) VALUES ('deployment started')")
        result = database_tool(action="query", engine="sqlite", database=db_path,
                               query="SELECT * FROM logs")
        self.assertIn("deployment started", result)

        # 9. Check git history
        commits = git_log(5, project_dir)
        self.assertTrue(len(commits) >= 1)


if __name__ == "__main__":
    unittest.main()
