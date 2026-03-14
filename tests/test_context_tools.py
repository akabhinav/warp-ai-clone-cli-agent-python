"""Tests for context tools — static configs and codebase index."""

import pytest

from pyoz.tools.context_tools import static_config, codebase_index


class TestStaticConfig:
    def test_java_config(self):
        result = static_config("java", "myapp")
        assert "pom.xml" in result
        assert "myapp" in result
        assert "junit-jupiter" in result
        assert "maven.compiler.source" in result

    def test_python_config(self):
        result = static_config("python", "myapp")
        assert "requirements.txt" in result
        assert "myapp" in result

    def test_go_config(self):
        result = static_config("go", "myapp")
        assert "go.mod" in result
        assert "myapp" in result

    def test_rust_config(self):
        result = static_config("rust", "myapp")
        assert "Cargo.toml" in result
        assert "myapp" in result

    def test_javascript_config(self):
        result = static_config("javascript", "myapp")
        assert "package.json" in result
        assert "myapp" in result
        assert "jest" in result

    def test_typescript_config(self):
        result = static_config("typescript", "myapp")
        assert "package.json" in result
        assert "typescript" in result

    def test_kotlin_config(self):
        result = static_config("kotlin", "myapp")
        assert "build.gradle.kts" in result

    def test_csharp_config(self):
        result = static_config("csharp", "myapp")
        assert ".csproj" in result

    def test_unknown_language(self):
        with pytest.raises(ValueError, match="No static config"):
            static_config("brainfuck", "myapp")

    def test_case_insensitive(self):
        result = static_config("Java", "myapp")
        assert "pom.xml" in result

    def test_project_name_substitution(self):
        result = static_config("java", "rule-engine")
        assert "rule-engine" in result


class TestCodebaseIndex:
    def test_empty_index(self):
        result = codebase_index(None)
        assert "No files indexed" in result

    def test_with_data(self):
        data = {
            "src/Rule.java": {
                "symbols": [
                    {"kind": "class", "name": "Rule", "detail": ""},
                    {"kind": "method", "name": "evaluate", "detail": "(Map<String,Object> facts) -> boolean"},
                ],
                "imports": ["java.util.List", "java.util.Map"],
                "dependencies": ["Condition"],
            }
        }
        result = codebase_index(data)
        assert "Rule.java" in result
        assert "class Rule" in result
        assert "method evaluate" in result
        assert "imports:" in result
        assert "depends on:" in result
