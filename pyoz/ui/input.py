"""PyOz input — enhanced input with history, autocomplete, and multiline."""

import os
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML

PYOZ_HOME = os.path.join(os.path.expanduser("~"), ".pyoz")
HISTORY_FILE = os.path.join(PYOZ_HOME, "input_history")

# All slash commands for autocomplete
SLASH_COMMANDS = [
    ("/help", "Show help"),
    ("/quit", "Exit PyOz"),
    ("/exit", "Exit PyOz"),
    ("/undo", "Undo last git commit"),
    ("/diff", "Show uncommitted changes"),
    ("/log", "Show recent git history"),
    ("/index", "Re-scan and re-index codebase"),
    ("/files", "List files in working directory"),
    ("/stats", "Show token usage and cost"),
    ("/clear", "Clear conversation history"),
    ("/rules", "Show loaded rules from PYOZ.md"),
    ("/save", "Save current session"),
    ("/resume", "Resume last saved session"),
    ("/new", "Archive current, start fresh"),
    ("/sessions", "List archived sessions"),
    ("/export", "Export session as markdown"),
    ("/workspace", "Show/switch workspaces"),
    ("/ws", "Show/switch workspaces"),
    ("/ws-add", "Add workspace"),
    ("/ws-remove", "Remove workspace"),
    ("/stream", "Toggle streaming output"),
]


class SlashCommandCompleter(Completer):
    """Autocomplete for slash commands."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        # Only complete at the start of input
        if not text.startswith("/"):
            return

        # Find matching commands
        for cmd, desc in SLASH_COMMANDS:
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )


# Prompt style
PROMPT_STYLE = PTStyle.from_dict({
    "prompt": "bold ansigreen",
    "": "",
})


class InputManager:
    """Manages user input with history, autocomplete, and key bindings."""

    def __init__(self):
        os.makedirs(PYOZ_HOME, exist_ok=True)

        # Key bindings
        self.kb = KeyBindings()

        # Ctrl+D to exit
        @self.kb.add("c-d")
        def _(event):
            event.app.exit(exception=EOFError())

        # Create prompt session with history and completion
        try:
            self.session = PromptSession(
                history=FileHistory(HISTORY_FILE),
                completer=SlashCommandCompleter(),
                complete_while_typing=False,
                key_bindings=self.kb,
                style=PROMPT_STYLE,
                enable_history_search=True,
            )
        except Exception:
            # Fallback if prompt_toolkit has issues
            self.session = None

    def get_input(self, prompt_text: str = "> ") -> str:
        """Get user input with enhanced features."""
        if self.session:
            try:
                return self.session.prompt(
                    HTML(f"<prompt>{prompt_text}</prompt>"),
                ).strip()
            except KeyboardInterrupt:
                raise
            except EOFError:
                raise
            except Exception:
                # Fallback to basic input
                return input(prompt_text).strip()
        else:
            return input(prompt_text).strip()

    def get_multiline_input(self, prompt_text: str = "... ") -> str:
        """Get multiline input (for pasting code blocks)."""
        if self.session:
            try:
                return self.session.prompt(
                    HTML(f"<prompt>{prompt_text}</prompt>"),
                    multiline=True,
                ).strip()
            except Exception:
                return input(prompt_text).strip()
        else:
            return input(prompt_text).strip()
