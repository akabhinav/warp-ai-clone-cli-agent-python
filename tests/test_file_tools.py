"""Tests for file tools."""

import os
import tempfile
import pytest

from pyoz.tools.file_tools import read_file, write_file, edit_file, search_files, list_directory


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestReadFile:
    def test_read_existing(self, tmpdir):
        path = os.path.join(tmpdir, "test.txt")
        with open(path, "w") as f:
            f.write("hello")
        assert read_file(path) == "hello"

    def test_read_missing(self, tmpdir):
        with pytest.raises(FileNotFoundError):
            read_file(os.path.join(tmpdir, "missing.txt"))


class TestWriteFile:
    def test_write_new(self, tmpdir):
        path = os.path.join(tmpdir, "new.txt")
        result = write_file(path, "content")
        assert "wrote" in result
        assert os.path.isfile(path)
        assert read_file(path) == "content"

    def test_write_creates_parent_dirs(self, tmpdir):
        path = os.path.join(tmpdir, "a", "b", "c", "deep.txt")
        write_file(path, "deep")
        assert read_file(path) == "deep"

    def test_write_overwrites(self, tmpdir):
        path = os.path.join(tmpdir, "over.txt")
        write_file(path, "first")
        write_file(path, "second")
        assert read_file(path) == "second"


class TestEditFile:
    def test_edit_replaces(self, tmpdir):
        path = os.path.join(tmpdir, "edit.txt")
        write_file(path, "hello world")
        result = edit_file(path, "hello", "goodbye")
        assert "edited" in result
        assert read_file(path) == "goodbye world"

    def test_edit_missing_file(self, tmpdir):
        with pytest.raises(FileNotFoundError):
            edit_file(os.path.join(tmpdir, "nope.txt"), "a", "b")

    def test_edit_text_not_found(self, tmpdir):
        path = os.path.join(tmpdir, "edit2.txt")
        write_file(path, "hello world")
        with pytest.raises(ValueError, match="not found"):
            edit_file(path, "xyz", "abc")

    def test_edit_text_duplicate(self, tmpdir):
        path = os.path.join(tmpdir, "dup.txt")
        write_file(path, "aaa bbb aaa")
        with pytest.raises(ValueError, match="2 times"):
            edit_file(path, "aaa", "ccc")


class TestSearchFiles:
    def test_search_finds_pattern(self, tmpdir):
        write_file(os.path.join(tmpdir, "a.py"), "def hello():\n    pass\n")
        write_file(os.path.join(tmpdir, "b.py"), "def world():\n    pass\n")
        results = search_files("hello", tmpdir)
        assert len(results) == 1
        assert results[0]["file"] == "a.py"
        assert results[0]["line"] == 1

    def test_search_with_ext_filter(self, tmpdir):
        write_file(os.path.join(tmpdir, "a.py"), "hello")
        write_file(os.path.join(tmpdir, "b.txt"), "hello")
        results = search_files("hello", tmpdir, file_ext=".py")
        assert len(results) == 1
        assert results[0]["file"] == "a.py"

    def test_search_no_matches(self, tmpdir):
        write_file(os.path.join(tmpdir, "a.py"), "hello")
        results = search_files("xyz", tmpdir)
        assert len(results) == 0

    def test_search_skips_git_dir(self, tmpdir):
        git_dir = os.path.join(tmpdir, ".git")
        os.makedirs(git_dir)
        write_file(os.path.join(git_dir, "config"), "hello")
        write_file(os.path.join(tmpdir, "a.py"), "hello")
        results = search_files("hello", tmpdir)
        assert len(results) == 1

    def test_search_invalid_regex(self, tmpdir):
        with pytest.raises(ValueError, match="Invalid regex"):
            search_files("[invalid", tmpdir)


class TestListDirectory:
    def test_list_files(self, tmpdir):
        write_file(os.path.join(tmpdir, "a.txt"), "x")
        write_file(os.path.join(tmpdir, "b.txt"), "y")
        entries = list_directory(tmpdir)
        names = [e["name"] for e in entries]
        assert "a.txt" in names
        assert "b.txt" in names

    def test_list_shows_types(self, tmpdir):
        write_file(os.path.join(tmpdir, "f.txt"), "x")
        os.makedirs(os.path.join(tmpdir, "subdir"))
        entries = list_directory(tmpdir)
        types = {e["name"]: e["type"] for e in entries}
        assert types["f.txt"] == "file"
        assert types["subdir"] == "directory"

    def test_list_skips_hidden(self, tmpdir):
        write_file(os.path.join(tmpdir, ".hidden"), "x")
        write_file(os.path.join(tmpdir, "visible.txt"), "y")
        entries = list_directory(tmpdir)
        names = [e["name"] for e in entries]
        assert ".hidden" not in names
        assert "visible.txt" in names

    def test_list_missing_dir(self):
        with pytest.raises(FileNotFoundError):
            list_directory("/nonexistent/dir/abc123")
