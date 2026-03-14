"""Tests for AST indexer."""

import os
import tempfile
import pytest

from pyoz.tools.file_tools import write_file
from pyoz.indexer.ast_indexer import ASTIndexer


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestPythonIndexing:
    def test_class_extraction(self, tmpdir):
        write_file(os.path.join(tmpdir, "models.py"), """
class User:
    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}"
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        assert indexer.file_count() == 1
        info = indexer.index["models.py"]
        names = [s["name"] for s in info["symbols"]]
        assert "User" in names

    def test_function_extraction(self, tmpdir):
        write_file(os.path.join(tmpdir, "utils.py"), """
def add(a: int, b: int) -> int:
    return a + b

def multiply(x, y):
    return x * y
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["utils.py"]
        names = [s["name"] for s in info["symbols"]]
        assert "add" in names
        assert "multiply" in names

    def test_import_extraction(self, tmpdir):
        write_file(os.path.join(tmpdir, "app.py"), """
import os
from typing import List
from pathlib import Path
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["app.py"]
        assert len(info["imports"]) >= 2


class TestJavaIndexing:
    def test_class_and_method(self, tmpdir):
        write_file(os.path.join(tmpdir, "Rule.java"), """
import java.util.List;
import java.util.Map;

public class Rule {
    private String name;

    public boolean evaluate(Map<String, Object> facts) {
        return true;
    }

    public void addCondition(Condition c) {
    }
}
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["Rule.java"]
        names = [s["name"] for s in info["symbols"]]
        assert "Rule" in names
        assert "evaluate" in names


class TestGoIndexing:
    def test_struct_and_func(self, tmpdir):
        write_file(os.path.join(tmpdir, "main.go"), """
package main

import "fmt"

type Server struct {
    host string
    port int
}

func (s *Server) Start() error {
    return nil
}

func NewServer(host string, port int) *Server {
    return &Server{host: host, port: port}
}
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["main.go"]
        names = [s["name"] for s in info["symbols"]]
        assert "Server" in names
        assert "Start" in names
        assert "NewServer" in names


class TestRustIndexing:
    def test_struct_and_impl(self, tmpdir):
        write_file(os.path.join(tmpdir, "lib.rs"), """
pub struct Config {
    name: String,
    value: i32,
}

impl Config {
    pub fn new(name: String) -> Config {
        Config { name, value: 0 }
    }
}

fn helper(x: i32) -> bool {
    x > 0
}
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["lib.rs"]
        names = [s["name"] for s in info["symbols"]]
        assert "Config" in names
        assert "new" in names or "helper" in names


class TestJavaScriptIndexing:
    def test_class_and_function(self, tmpdir):
        write_file(os.path.join(tmpdir, "app.js"), """
class EventEmitter {
    constructor() {
        this.listeners = {};
    }
}

function createApp(config) {
    return new EventEmitter();
}

const helper = (x) => x * 2;
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        info = indexer.index["app.js"]
        names = [s["name"] for s in info["symbols"]]
        assert "EventEmitter" in names
        assert "createApp" in names


class TestReindexing:
    def test_reindex_after_write(self, tmpdir):
        path = os.path.join(tmpdir, "test.py")
        write_file(path, "def foo(): pass\n")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        assert indexer.symbol_count() >= 1

        # Modify file
        write_file(path, "def foo(): pass\ndef bar(): pass\n")
        indexer.reindex_file(path)
        assert indexer.symbol_count() >= 2

    def test_reindex_deleted_file(self, tmpdir):
        path = os.path.join(tmpdir, "del.py")
        write_file(path, "def x(): pass\n")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        assert indexer.file_count() == 1

        os.remove(path)
        indexer.reindex_file(path)
        assert indexer.file_count() == 0


class TestSummary:
    def test_summary_format(self, tmpdir):
        write_file(os.path.join(tmpdir, "demo.py"), """
class Demo:
    def run(self):
        pass
""")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        summary = indexer.get_summary()
        assert "FILE:" in summary
        assert "demo.py" in summary

    def test_empty_summary(self, tmpdir):
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        summary = indexer.get_summary()
        assert "No files indexed" in summary


class TestSkipDirs:
    def test_skips_node_modules(self, tmpdir):
        nm = os.path.join(tmpdir, "node_modules", "pkg")
        os.makedirs(nm)
        write_file(os.path.join(nm, "index.js"), "function x() {}")
        write_file(os.path.join(tmpdir, "app.js"), "function y() {}")
        indexer = ASTIndexer(tmpdir)
        indexer.scan()
        assert indexer.file_count() == 1
        assert "app.js" in indexer.index
