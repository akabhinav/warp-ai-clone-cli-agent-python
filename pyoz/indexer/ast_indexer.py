"""AST Indexer — tree-sitter with regex fallback.

Parses source files and extracts classes, methods, fields, functions,
imports, and dependencies as structured summaries.
"""

import os
import re
from typing import Any

SKIP_DIRS = {".git", "node_modules", "target", "build", "venv", "__pycache__", ".venv", "dist", ".tox", ".mypy_cache", ".idea", ".vscode"}

# File extensions we can index
INDEXABLE_EXTENSIONS = {
    ".py", ".java", ".go", ".rs", ".js", ".jsx", ".ts", ".tsx",
    ".kt", ".kts", ".cs", ".rb", ".cpp", ".c", ".h", ".hpp",
}

# Try to import tree-sitter; fall back to regex if unavailable
_tree_sitter_available = False
try:
    import tree_sitter_languages
    _tree_sitter_available = True
except ImportError:
    pass


class ASTIndexer:
    """Index source files using tree-sitter AST or regex fallback."""

    def __init__(self, root_dir: str | None = None):
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.getcwd()
        self.index: dict[str, dict[str, Any]] = {}

    def scan(self) -> dict[str, dict[str, Any]]:
        """Scan all source files and build the index."""
        self.index.clear()
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in INDEXABLE_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.root_dir)
                try:
                    self.index[rel_path] = self._index_file(fpath, ext)
                except Exception:
                    self.index[rel_path] = {"symbols": [], "imports": [], "dependencies": []}
        return self.index

    def reindex_file(self, file_path: str) -> None:
        """Re-index a single file after modification."""
        abs_path = os.path.abspath(file_path)
        rel_path = os.path.relpath(abs_path, self.root_dir)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in INDEXABLE_EXTENSIONS and os.path.isfile(abs_path):
            try:
                self.index[rel_path] = self._index_file(abs_path, ext)
            except Exception:
                pass
        elif rel_path in self.index and not os.path.exists(abs_path):
            del self.index[rel_path]

    def _index_file(self, path: str, ext: str) -> dict[str, Any]:
        """Index a single file."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()

        if _tree_sitter_available:
            return self._index_with_treesitter(source, ext)
        return self._index_with_regex(source, ext)

    def _index_with_treesitter(self, source: str, ext: str) -> dict[str, Any]:
        """Use tree-sitter for AST parsing."""
        lang_map = {
            ".py": "python", ".java": "java", ".go": "go", ".rs": "rust",
            ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
            ".tsx": "typescript", ".kt": "kotlin", ".rb": "ruby",
            ".cpp": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp",
            ".cs": "c_sharp",
        }
        lang_name = lang_map.get(ext)
        if not lang_name:
            return self._index_with_regex(source, ext)

        try:
            parser = tree_sitter_languages.get_parser(lang_name)
            tree = parser.parse(source.encode("utf-8"))
            return self._extract_from_tree(tree.root_node, source, lang_name)
        except Exception:
            return self._index_with_regex(source, ext)

    def _extract_from_tree(self, root, source: str, lang: str) -> dict[str, Any]:
        """Extract symbols from tree-sitter AST."""
        symbols = []
        imports = []
        dependencies = set()

        def visit(node, parent_class=None):
            ntype = node.type

            # Classes/structs
            if ntype in ("class_definition", "class_declaration", "struct_item",
                         "struct_specifier", "interface_declaration"):
                name = self._get_child_text(node, "name", source) or self._get_child_text(node, "type_identifier", source)
                kind = "struct" if "struct" in ntype else "interface" if "interface" in ntype else "class"
                if name:
                    symbols.append({"kind": kind, "name": name, "detail": ""})
                    for child in node.children:
                        visit(child, parent_class=name)
                return

            # Functions/methods
            if ntype in ("function_definition", "method_declaration", "function_declaration",
                         "function_item", "method_definition"):
                name = self._get_child_text(node, "name", source) or self._get_child_text(node, "identifier", source)
                if name:
                    kind = "method" if parent_class else "function"
                    params = self._get_child_text(node, "parameters", source) or self._get_child_text(node, "formal_parameters", source) or ""
                    ret = self._get_return_type(node, source)
                    detail = f"({params})" if params else "()"
                    if ret:
                        detail += f" -> {ret}"
                    symbols.append({"kind": kind, "name": name, "detail": detail})
                return

            # Fields
            if ntype in ("field_declaration", "field_definition") and parent_class:
                text = source[node.start_byte:node.end_byte].strip()
                name = text.split()[1] if len(text.split()) > 1 else text
                symbols.append({"kind": "field", "name": name.rstrip(";"), "detail": ""})

            # Imports
            if ntype in ("import_statement", "import_declaration", "use_declaration",
                         "include_statement", "import_from_statement"):
                text = source[node.start_byte:node.end_byte].strip()
                imports.append(text)
                # Extract dependency
                parts = text.replace("import ", "").replace("from ", "").split(".")
                if len(parts) > 0:
                    dep = parts[-1].strip().rstrip(";").strip("\"'")
                    if dep and dep not in ("*",):
                        dependencies.add(dep)

            for child in node.children:
                visit(child, parent_class)

        visit(root)
        return {"symbols": symbols, "imports": imports, "dependencies": sorted(dependencies)}

    def _get_child_text(self, node, field_name: str, source: str) -> str | None:
        """Get text of a named child node."""
        child = node.child_by_field_name(field_name)
        if child:
            return source[child.start_byte:child.end_byte]
        # Fallback: search children by type
        for c in node.children:
            if c.type == field_name:
                return source[c.start_byte:c.end_byte]
        return None

    def _get_return_type(self, node, source: str) -> str | None:
        """Extract return type annotation."""
        ret = node.child_by_field_name("return_type") or node.child_by_field_name("type")
        if ret:
            return source[ret.start_byte:ret.end_byte]
        return None

    def _index_with_regex(self, source: str, ext: str) -> dict[str, Any]:
        """Fallback regex-based indexing for any language."""
        symbols = []
        imports = []
        dependencies = set()

        lines = source.splitlines()

        for line in lines:
            stripped = line.strip()

            # Imports (many languages)
            if re.match(r'^(import |from |use |require|#include|using )', stripped):
                imports.append(stripped)
                # Extract dependency name
                m = re.search(r'(?:import|from|use|require)\s+["\']?([A-Za-z_][\w.]*)', stripped)
                if m:
                    dep = m.group(1).split(".")[-1]
                    dependencies.add(dep)
                continue

            # Python class
            m = re.match(r'^class\s+(\w+)(?:\(([^)]*)\))?:', stripped)
            if m:
                symbols.append({"kind": "class", "name": m.group(1), "detail": f"({m.group(2)})" if m.group(2) else ""})
                continue

            # Python function/method
            m = re.match(r'^(\s*)def\s+(\w+)\(([^)]*)\)(?:\s*->\s*(.+))?:', stripped)
            if m:
                indent = len(m.group(1)) if m.group(1) else 0
                kind = "method" if indent > 0 else "function"
                ret = m.group(4).strip().rstrip(":") if m.group(4) else None
                detail = f"({m.group(3)})"
                if ret:
                    detail += f" -> {ret}"
                symbols.append({"kind": kind, "name": m.group(2), "detail": detail})
                continue

            # Java/C#/Kotlin class
            m = re.match(r'^(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?(?:class|interface|enum)\s+(\w+)', stripped)
            if m:
                kind = "interface" if "interface" in stripped else "enum" if "enum" in stripped else "class"
                symbols.append({"kind": kind, "name": m.group(1), "detail": ""})
                continue

            # Java/C# method
            m = re.match(r'^(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)\(([^)]*)\)', stripped)
            if m and m.group(1) not in ("if", "for", "while", "switch", "catch", "new", "return"):
                symbols.append({"kind": "method", "name": m.group(2), "detail": f"({m.group(3)}) -> {m.group(1)}"})
                continue

            # Go struct
            m = re.match(r'^type\s+(\w+)\s+struct\s*\{', stripped)
            if m:
                symbols.append({"kind": "struct", "name": m.group(1), "detail": ""})
                continue

            # Go func
            m = re.match(r'^func\s+(?:\((\w+)\s+\*?(\w+)\)\s+)?(\w+)\(([^)]*)\)(?:\s+(.+))?\s*\{', stripped)
            if m:
                kind = "method" if m.group(1) else "function"
                name = m.group(3)
                params = m.group(4)
                ret = m.group(5) if m.group(5) else None
                detail = f"({params})"
                if ret:
                    detail += f" -> {ret}"
                symbols.append({"kind": kind, "name": name, "detail": detail})
                continue

            # Rust struct
            m = re.match(r'^(?:pub\s+)?struct\s+(\w+)', stripped)
            if m:
                symbols.append({"kind": "struct", "name": m.group(1), "detail": ""})
                continue

            # Rust impl
            m = re.match(r'^impl(?:<[^>]*>)?\s+(\w+)', stripped)
            if m:
                symbols.append({"kind": "impl", "name": m.group(1), "detail": ""})
                continue

            # Rust fn
            m = re.match(r'^(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\(([^)]*)\)(?:\s*->\s*(.+))?\s*\{', stripped)
            if m:
                detail = f"({m.group(2)})"
                if m.group(3):
                    detail += f" -> {m.group(3).strip().rstrip('{').strip()}"
                symbols.append({"kind": "function", "name": m.group(1), "detail": detail})
                continue

            # JavaScript/TypeScript class
            m = re.match(r'^(?:export\s+)?(?:default\s+)?class\s+(\w+)', stripped)
            if m:
                symbols.append({"kind": "class", "name": m.group(1), "detail": ""})
                continue

            # JavaScript/TypeScript function
            m = re.match(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\(([^)]*)\)', stripped)
            if m:
                symbols.append({"kind": "function", "name": m.group(1), "detail": f"({m.group(2)})"})
                continue

            # Const arrow function
            m = re.match(r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>', stripped)
            if m:
                symbols.append({"kind": "function", "name": m.group(1), "detail": ""})
                continue

        return {"symbols": symbols, "imports": imports, "dependencies": sorted(dependencies)}

    def get_summary(self) -> str:
        """Get a human-readable summary of the index."""
        from pyoz.tools.context_tools import codebase_index
        return codebase_index(self.index)

    def file_count(self) -> int:
        return len(self.index)

    def symbol_count(self) -> int:
        total = 0
        for info in self.index.values():
            if isinstance(info, dict):
                total += len(info.get("symbols", []))
        return total
