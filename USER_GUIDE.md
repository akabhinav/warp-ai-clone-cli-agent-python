# PyOz User Guide

**Your AI Coding Assistant — Right in Your Terminal**

PyOz is like having a senior developer sitting next to you. You type what you want in plain English, and PyOz writes the code, runs it, fixes errors, and manages everything — all automatically.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Your First Conversation](#2-your-first-conversation)
3. [Understanding the Screen](#3-understanding-the-screen)
4. [Talking to PyOz](#4-talking-to-pyoz)
5. [Slash Commands Reference](#5-slash-commands-reference)
6. [Working with Projects](#6-working-with-projects)
7. [Managing Sessions](#7-managing-sessions)
8. [Switching Between Projects](#8-switching-between-projects)
9. [Keyboard Shortcuts](#9-keyboard-shortcuts)
10. [Real-World Examples](#10-real-world-examples)
11. [Settings & Customization](#11-settings--customization)
12. [Troubleshooting](#12-troubleshooting)
13. [Glossary](#13-glossary)

---

## 1. Getting Started

### What You Need

- **Python 3.11 or newer** installed on your computer
- **An API key** from one of these services:
  - [Anthropic (Claude)](https://console.anthropic.com/) — recommended, best results
  - [OpenAI (GPT-4)](https://platform.openai.com/) — great alternative
  - [Ollama](https://ollama.ai/) — free, runs on your computer, no API key needed

### Installation

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and type:

```
pip install httpx rich prompt_toolkit
```

### Starting PyOz

**Option A: Using Claude (recommended)**
```
export ANTHROPIC_API_KEY=your-key-here
python pyoz.py --provider claude
```

**Option B: Using OpenAI**
```
export OPENAI_API_KEY=your-key-here
python pyoz.py --provider openai
```

**Option C: Using Ollama (free, no API key)**
```
ollama pull qwen2.5:7b
python pyoz.py --provider ollama --model qwen2.5:7b
```

> **Tip for Windows users:** Use `set` instead of `export`:
> ```
> set ANTHROPIC_API_KEY=your-key-here
> python pyoz.py --provider claude
> ```

### Verify It Works

Run the built-in self-test to make sure everything is set up correctly:

```
python pyoz.py --test
```

You should see green checkmarks (✓) for all 16 tests.

---

## 2. Your First Conversation

When PyOz starts, you'll see a welcome screen:

```
╭─ 🧙 PyOz — Coding Agent ────────────────────────────────╮
│                                                           │
│   Provider: claude / claude-sonnet-4-20250514             │
│   ✓ AST Indexer ready                                     │
│   ✓ Codebase: 0 files, 0 symbols                         │
│   ✓ Git: no repo                                          │
│   ○ Rules: none (create PYOZ.md to add)                   │
│                                                           │
│   Type /help for commands  •  Ctrl+C to interrupt         │
╰───────────────────────────────────────────────────────────╯
```

Now just type what you want! Here's your first conversation:

```
> hello, what can you do?

I'm PyOz, your coding assistant! I can:

- **Create projects** from scratch in any programming language
- **Edit code** to fix bugs or add features
- **Run commands** like builds and tests
- **Search your codebase** to understand existing code
- **Use git** to track all changes automatically

Just tell me what you want to build, fix, or explore!

  ✓ done  🔧 0 calls  🧠 245↑ 89↓  ⏱ $0.00
```

That's it. Just type naturally, like you're talking to a colleague.

---

## 3. Understanding the Screen

### The Prompt

```
>
```

This is where you type. The green `>` means PyOz is ready for your input.

### Tool Calls

When PyOz works on your request, you'll see what it's doing in real time:

```
  → write_file src/app.py (523 bytes)
  → run_command python src/app.py
  │ Hello, World!
  │ Exit code: 0
  → git_commit "create hello world app"
```

Here's what each part means:

| Symbol | Meaning |
|--------|---------|
| `→` | PyOz is performing an action |
| `write_file` | Creating or overwriting a file |
| `read_file` | Reading a file to understand it |
| `edit_file` | Making a small change to a file |
| `run_command` | Running a terminal command |
| `search_files` | Searching your code for something |
| `│` | Output from a command |

### The Summary Line

After every response, you'll see a summary:

```
  ✓ done  🔧 4 calls  🧠 1,234↑ 567↓  ⏱ $0.02
```

| Part | Meaning |
|------|---------|
| `✓ done` | PyOz finished successfully |
| `🔧 4 calls` | Used 4 tools (file writes, commands, etc.) |
| `🧠 1,234↑ 567↓` | Tokens used (↑ = input, ↓ = output) |
| `⏱ $0.02` | Estimated cost of this turn |

### Diffs (Code Changes)

When PyOz edits a file, you'll see what changed:

```
  src/app.py:
  - print("Hello")
  + print("Hello, World!")
```

- **Red lines (-)**: What was removed
- **Green lines (+)**: What was added

---

## 4. Talking to PyOz

You don't need to know programming jargon. Just describe what you want in plain English.

### Creating Something New

```
> create a simple calculator in Python
```

```
> make a website landing page with a signup form
```

```
> build a todo list app in JavaScript
```

### Fixing Problems

```
> the app crashes when I click submit, can you fix it?
```

```
> there's a typo in the welcome message, change it to "Welcome aboard!"
```

```
> the tests are failing, please fix them
```

### Understanding Code

```
> what does the login function do?
```

```
> explain how the database connection works
```

```
> show me all the files in this project
```

### Modifying Code

```
> add a dark mode toggle to the settings page
```

```
> rename the User class to Customer everywhere
```

```
> add error handling to the API calls
```

### Running Things

```
> run the tests
```

```
> start the development server
```

```
> install the project dependencies
```

### Tips for Better Results

1. **Be specific**: "add a blue submit button to the contact form" works better than "make the form better"
2. **One thing at a time**: Ask for one change per message for best results
3. **Give context**: "the login page at src/pages/login.js isn't showing the error message" is better than "login is broken"
4. **Ask follow-ups**: If the first result isn't right, just say "that's not quite right, I meant..."

---

## 5. Slash Commands Reference

Slash commands start with `/` and are shortcuts for common actions. Type them at the prompt.

### Quick Reference Card

```
/help        Show all commands
/quit        Save and exit

/undo        Undo the last change
/diff        Show what changed since last commit
/log         Show recent change history

/files       List project files
/index       Re-scan the codebase
/rules       Show project rules

/save        Save conversation
/resume      Continue previous conversation
/new         Start fresh conversation
/sessions    View saved conversations
/export      Export conversation as a document

/ws          Show your projects
/ws myapp    Switch to a project
/ws-add      Add current folder as project
/ws-remove 2 Remove project #2

/stream      Toggle fast streaming mode
/stats       Show usage statistics
```

### Detailed Examples

#### `/undo` — Undo the Last Change

Made a mistake? Undo it instantly:

```
> add a footer to the page

  → edit_file src/index.html
  ✓ done

> hmm, I don't like that footer

> /undo
  ✓ reverted commit a1b2c3d
```

The file is back to how it was before.

#### `/diff` — See What Changed

See all uncommitted changes in your project:

```
> /diff
  src/app.py:
  - old_function()
  + new_function()

  src/config.py:
  + DEBUG = True
```

#### `/log` — View History

See your recent changes:

```
> /log
  a1b2c3d pyoz: create app.py
  e4f5g6h pyoz: add login feature
  i7j8k9l pyoz: fix test failures
```

#### `/files` — List Project Files

See what's in your project:

```
> /files
  src/
  tests/
  README.md (1,234 bytes)
  requirements.txt (45 bytes)
  setup.py (567 bytes)
```

#### `/stats` — Check Your Usage

See how many tokens and dollars you've used:

```
> /stats
  Turns           5
  Tool calls      23
  Input tokens    12,456
  Output tokens   5,678
  Estimated cost  $0.12
```

#### `/stream` — Toggle Streaming

Streaming shows the response word-by-word as PyOz thinks, instead of waiting for the full answer:

```
> /stream
  ✓ Streaming: on
```

Now responses will appear gradually, like someone typing in real time.

---

## 6. Working with Projects

### Starting in a Project Folder

Navigate to your project folder before starting PyOz:

```
cd ~/my-project
python pyoz.py --provider claude
```

Or specify the folder directly:

```
python pyoz.py --provider claude --work-dir ~/my-project
```

### PyOz Automatically Understands Your Code

When PyOz starts, it scans your project and builds a map of all your code:

```
  ✓ Codebase: 47 files, 312 symbols
```

This means PyOz knows about all your classes, functions, and imports — without reading every file in full. When it needs more detail, it reads specific files on demand.

### Setting Project Rules

Create a file called `PYOZ.md` in your project root to set rules that PyOz always follows:

```markdown
# Project Rules

- Use Python 3.11 with type hints
- Write tests for every new function
- Follow PEP 8 style guidelines
- Use pytest for testing
- Never use print() in production code — use the logger
```

Once this file exists, PyOz will follow these rules for every change it makes in this project.

```
> /rules
  # Project Rules
  - Use Python 3.11 with type hints
  - Write tests for every new function
  ...
```

### How Git Works Automatically

Every time PyOz creates or edits a file, it automatically saves a checkpoint using git. You'll see messages like:

```
  → write_file src/utils.py (234 bytes)
```

Behind the scenes, PyOz runs `git commit` with a descriptive message like "pyoz: create utils.py". This means:

- **You can always undo** with `/undo`
- **Nothing is ever lost** — every change is saved
- **You can see the full history** with `/log`

If your project isn't a git repository yet, PyOz will initialize one automatically when it first creates files.

---

## 7. Managing Sessions

Sessions save your conversation so you can continue later.

### Automatic Saving

PyOz automatically saves your conversation after every message. When you restart, it picks up right where you left off:

```
🧙 PyOz — Coding Agent
  ✓ Session: resumed (12 turns)
```

### Starting Fresh

If you want to start a new conversation:

```
> /new
  ✓ Previous session archived. Starting fresh.
```

Your old conversation is saved in the archive — not deleted.

### Viewing Past Sessions

```
> /sessions
  Archived sessions:
  #  Date                  Turns  Provider
  1  2026-03-14 14:30:22   12     claude
  2  2026-03-13 09:15:00   8      claude
  3  2026-03-12 16:45:33   23     openai
```

### Exporting a Session

Save your conversation as a readable document:

```
> /export
  ✓ Session exported to: /home/user/myproject/pyoz_session.md
```

This creates a markdown file you can share, read, or keep for reference.

### Skipping Session Resume

If you always want to start fresh:

```
python pyoz.py --provider claude --no-resume
```

---

## 8. Switching Between Projects

PyOz remembers your recent projects so you can switch between them easily.

### View Your Projects

```
> /ws
  Current: /home/user/web-app

  Recent workspaces:
  #  Name       Path                      Last Access
  1  web-app    /home/user/web-app    ←   2026-03-14 14:30
  2  api-server /home/user/api-server     2026-03-13 09:15
  3  mobile-app /home/user/mobile-app     2026-03-12 16:45
```

The `←` arrow shows which project you're currently in.

### Switch to Another Project

By number:
```
> /ws 2
  ✓ Switched to: api-server (/home/user/api-server)
    23 files indexed, 156 symbols
    Resumed session (8 turns)
```

By name:
```
> /ws mobile-app
  ✓ Switched to: mobile-app (/home/user/mobile-app)
```

By path:
```
> /ws /home/user/new-project
  ✓ Switched to: new-project (/home/user/new-project)
```

### Add a New Project

```
> /ws-add /home/user/another-project
  ✓ Added workspace: another-project
```

Or add the current directory:
```
> /ws-add
  ✓ Added workspace: my-current-folder
```

### Remove a Project

```
> /ws-remove 3
  ✓ Removed workspace: 3
```

### What Happens When You Switch

When you switch projects, PyOz:

1. **Saves** your current conversation
2. **Switches** to the new project folder
3. **Re-scans** all the code in the new project
4. **Loads** the saved conversation for that project (if any)
5. **Loads** the project rules from PYOZ.md (if any)

Each project has its own separate conversation history.

---

## 9. Keyboard Shortcuts

### While Typing

| Shortcut | What it does |
|----------|-------------|
| `Enter` | Send your message |
| `Tab` | Autocomplete slash commands |
| `↑` / `↓` | Browse previous messages (history) |
| `Ctrl+R` | Search through your message history |
| `Ctrl+C` | Cancel current operation |
| `Ctrl+C` twice | Force quit PyOz |
| `Ctrl+D` | Exit PyOz (same as `/quit`) |

### Tab Autocomplete

Start typing a slash command and press `Tab`:

```
> /wo[Tab]

> /workspace
```

You'll see a list of matching commands with descriptions to choose from.

### History Search

Press `Ctrl+R` and start typing to search your previous messages:

```
(reverse-i-search)`calc`: create a calculator in Python
```

Press `Enter` to use the found message, or `Ctrl+C` to cancel the search.

---

## 10. Real-World Examples

### Example 1: Creating a Project from Scratch

```
> create a Python REST API for a bookstore with endpoints
  for listing books, adding a book, and getting book details

  → static_config python/bookstore-api
  → write_file bookstore/requirements.txt (45 bytes)
  → write_file bookstore/app.py (1,234 bytes)
  → write_file bookstore/models.py (567 bytes)
  → write_file bookstore/routes.py (890 bytes)
  → write_file bookstore/tests/test_api.py (678 bytes)
  → run_command cd bookstore && pip install -r requirements.txt
  │ Successfully installed flask...
  → run_command cd bookstore && python -m pytest
  │ 6 passed in 0.3s
  ✓ done  🔧 8 calls  🧠 3,456↑ 2,345↓  ⏱ $0.08

Created a Flask REST API with:
- GET /books — list all books
- POST /books — add a new book
- GET /books/<id> — get book details
All 6 tests passing.
```

### Example 2: Fixing a Bug

```
> the app shows "undefined" instead of the username on the profile page

  → search_files pattern=username
  → read_file src/pages/Profile.js
  → edit_file src/pages/Profile.js
  → run_command npm test

  src/pages/Profile.js:
  - <h1>{user.username}</h1>
  + <h1>{user?.name || "Guest"}</h1>

  ✓ done  🔧 4 calls

Fixed! The issue was that the Profile page was trying to
access `user.username` but the API returns `user.name`.
I also added a fallback to "Guest" in case the user data
hasn't loaded yet.
```

### Example 3: Exploring Code You Didn't Write

```
> I just joined this project. Can you explain the architecture?

I've analyzed the codebase. Here's how it's organized:

**Architecture Overview:**
- **src/api/** — REST API endpoints (Express.js)
- **src/services/** — Business logic layer
- **src/models/** — Database models (PostgreSQL via Sequelize)
- **src/middleware/** — Auth, logging, error handling
- **src/utils/** — Shared helper functions

**Key Patterns:**
- Routes → Controllers → Services → Models
- JWT authentication via middleware
- All errors go through centralized error handler

**Entry Point:** `src/index.js` starts the Express server on port 3000.
```

### Example 4: Multi-Step Task

```
> add user authentication with login and signup

  → codebase_index
  → write_file src/models/User.js (456 bytes)
  → write_file src/services/AuthService.js (789 bytes)
  → write_file src/routes/auth.js (567 bytes)
  → edit_file src/app.js
  → write_file src/middleware/requireAuth.js (234 bytes)
  → write_file tests/auth.test.js (890 bytes)
  → run_command npm test
  │ 12 passed, 0 failed
  ✓ done  🔧 8 calls

Added authentication:
- **User model** with hashed passwords (bcrypt)
- **POST /auth/signup** — create account
- **POST /auth/login** — get JWT token
- **requireAuth middleware** — protect routes
- All 12 tests passing.

> now protect the /books endpoints so only logged-in users can access them

  → read_file src/routes/books.js
  → edit_file src/routes/books.js
  → edit_file tests/books.test.js
  → run_command npm test
  │ 18 passed, 0 failed
  ✓ done  🔧 4 calls

Done! All /books routes now require authentication.
Updated tests to include auth headers.
```

### Example 5: Using Undo

```
> rename all variables from camelCase to snake_case

  → search_files pattern=camelCase
  → edit_file src/utils.js
  → edit_file src/app.js
  → edit_file src/config.js
  ✓ done

> actually, let's keep camelCase. undo that.

> /undo
  ✓ reverted commit f3a4b5c

> /undo
  ✓ reverted commit d2e3f4a

> /undo
  ✓ reverted commit a1b2c3d

Everything is back to normal.
```

---

## 11. Settings & Customization

### Startup Options

```
python pyoz.py [options]
```

| Option | Description | Example |
|--------|-------------|---------|
| `--provider` | AI provider | `--provider claude` |
| `--api-key` | API key | `--api-key sk-ant-...` |
| `--model` | Specific model | `--model gpt-4o` |
| `--work-dir` | Project folder | `--work-dir ~/myapp` |
| `--stream` | Enable streaming | `--stream` |
| `--no-resume` | Start fresh | `--no-resume` |
| `--ollama-url` | Ollama server | `--ollama-url http://localhost:11434` |
| `--test` | Run self-test | `--test` |

### Using Environment Variables

Instead of typing the API key every time, set it permanently:

**Mac/Linux** — Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export ANTHROPIC_API_KEY=your-key-here
```

**Windows** — Set in System Settings → Environment Variables, or:
```
setx ANTHROPIC_API_KEY your-key-here
```

### Project Rules (PYOZ.md)

Create `PYOZ.md` in your project root. Here are some examples:

**For a Python project:**
```markdown
# Rules
- Python 3.11+ with type hints
- Use pytest for tests
- Follow PEP 8 style
- Use logging instead of print()
```

**For a JavaScript project:**
```markdown
# Rules
- Use TypeScript strict mode
- Use ESLint with Airbnb config
- Write Jest tests for all functions
- Use async/await, never callbacks
```

**For a Java project:**
```markdown
# Rules
- Java 17 with Maven
- JUnit 5 for tests
- Follow Google Java Style Guide
- All classes must have Javadoc
```

### Where PyOz Stores Data

All PyOz data is stored in `~/.pyoz/`:

```
~/.pyoz/
  workspaces.json     ← Your project list
  input_history       ← Your command history
  sessions/           ← Saved conversations
    abc123/
      session.json    ← Current session for a project
      history/        ← Archived sessions
```

---

## 12. Troubleshooting

### "Error: --api-key or ANTHROPIC_API_KEY required"

You haven't set your API key. Either:
```bash
# Set it for this session
export ANTHROPIC_API_KEY=your-key-here

# Or pass it directly
python pyoz.py --provider claude --api-key your-key-here
```

### "Cannot connect to Ollama"

Make sure Ollama is running:
```bash
ollama serve
```

Then in another terminal:
```bash
python pyoz.py --provider ollama
```

### "Claude API 401: invalid key"

Your API key is wrong or expired. Get a new one from:
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

### PyOz Seems Stuck

Press `Ctrl+C` once to interrupt the current operation. PyOz will stop what it's doing and wait for your next message.

Press `Ctrl+C` twice to force quit.

### "Command timed out"

Some commands take longer than 2 minutes (the default timeout). This is normal for things like:
- Installing dependencies (`npm install`, `pip install`)
- Running large test suites
- Building big projects

Try running the command separately in your terminal.

### Self-Test Fails

Run the self-test to diagnose issues:
```bash
python pyoz.py --test
```

If specific tests fail:
- **File tools fail**: Check file permissions in your current directory
- **Git tools fail**: Make sure `git` is installed (`git --version`)
- **UI fails**: Try `pip install rich prompt_toolkit` again

### Want to Start Completely Fresh

Delete PyOz's data folder:
```bash
rm -rf ~/.pyoz
```

This removes all saved sessions, workspace history, and command history.

---

## 13. Glossary

| Term | Meaning |
|------|---------|
| **API key** | A password-like string that lets PyOz talk to AI services (Claude, OpenAI) |
| **AST** | Abstract Syntax Tree — how PyOz understands your code structure without reading every line |
| **Codebase** | All the code files in your project |
| **Commit** | A saved snapshot of your code changes (like a save point in a video game) |
| **Diff** | A comparison showing what changed between two versions of a file |
| **Git** | A version control system that tracks every change to your code |
| **Index** | PyOz's internal map of all classes, functions, and imports in your project |
| **LLM** | Large Language Model — the AI brain (Claude, GPT-4, etc.) |
| **Ollama** | A free tool that runs AI models on your own computer |
| **Provider** | The AI service PyOz uses (Claude, OpenAI, or Ollama) |
| **REPL** | Read-Eval-Print Loop — the interactive prompt where you type commands |
| **Session** | Your conversation history with PyOz in a project |
| **Slash command** | Commands starting with `/` (like `/help`, `/undo`) |
| **Streaming** | Showing the AI's response word-by-word as it thinks |
| **Terminal** | The text-based interface where you run commands (also called command line or console) |
| **Token** | A small unit of text — roughly one word. Used to measure AI usage and cost |
| **Tool call** | When PyOz uses a tool like reading a file or running a command |
| **Workspace** | A project folder that PyOz manages |

---

## Quick Start Cheat Sheet

```
┌─────────────────────────────────────────────────────────┐
│                   PyOz Quick Start                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  START:     python pyoz.py --provider claude             │
│  TEST:      python pyoz.py --test                       │
│                                                         │
│  TALK:      Just type what you want in English          │
│  UNDO:      /undo                                       │
│  HISTORY:   /log                                        │
│  FILES:     /files                                      │
│  HELP:      /help                                       │
│  QUIT:      /quit  or  Ctrl+D                           │
│                                                         │
│  AUTOCOMPLETE:  Type /  then press Tab                  │
│  PAST MESSAGES: Press ↑ arrow key                       │
│  SEARCH HISTORY: Ctrl+R                                 │
│  INTERRUPT:     Ctrl+C                                  │
│                                                         │
│  SAVE WORK:     /save                                   │
│  SWITCH PROJECT: /ws project-name                       │
│  START FRESH:   /new                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

*PyOz v0.1.0 — Pure Agent Mode Coding Assistant*
