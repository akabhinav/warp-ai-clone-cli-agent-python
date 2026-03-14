#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# PyOz Installer — Linux / macOS / WSL
# Usage:  curl -sSL <raw-url>/install.sh | bash
#   or:   ./install.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

REPO="https://github.com/akabhinav/warp-ai-clone-cli-agent-python.git"
INSTALL_DIR="${PYOZ_HOME:-$HOME/.pyoz}"
MIN_PYTHON="3.11"

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${CYAN}[pyoz]${NC} $*"; }
ok()    { echo -e "${GREEN}[pyoz]${NC} $*"; }
warn()  { echo -e "${YELLOW}[pyoz]${NC} $*"; }
die()   { echo -e "${RED}[pyoz]${NC} $*" >&2; exit 1; }

# ── Check Python ──────────────────────────────────────────────
check_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [ "$(printf '%s\n' "$MIN_PYTHON" "$ver" | sort -V | head -n1)" = "$MIN_PYTHON" ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# ── Check git ─────────────────────────────────────────────────
command -v git &>/dev/null || die "git is required. Install it first."

# ── Find Python ───────────────────────────────────────────────
if ! check_python; then
    die "Python $MIN_PYTHON+ is required. Install from https://python.org"
fi
info "Using $PYTHON ($($PYTHON --version 2>&1))"

# ── Clone or update ───────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet origin main 2>/dev/null || git pull --quiet
else
    info "Cloning PyOz into $INSTALL_DIR..."
    git clone --depth 1 "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── Create venv ───────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR/venv" ]; then
    info "Creating virtual environment..."
    $PYTHON -m venv "$INSTALL_DIR/venv"
fi

# ── Install ───────────────────────────────────────────────────
info "Installing dependencies..."
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -e "$INSTALL_DIR"

# ── Create launcher script ───────────────────────────────────
LAUNCHER="$INSTALL_DIR/venv/bin/pyoz"
BIN_DIR=""

# Determine where to symlink
for dir in "$HOME/.local/bin" "$HOME/bin" "/usr/local/bin"; do
    if [ -d "$dir" ] || mkdir -p "$dir" 2>/dev/null; then
        BIN_DIR="$dir"
        break
    fi
done

if [ -n "$BIN_DIR" ]; then
    ln -sf "$LAUNCHER" "$BIN_DIR/pyoz"
    ok "Installed 'pyoz' command to $BIN_DIR/pyoz"

    # Check if BIN_DIR is in PATH
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
        warn "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo -e "  ${CYAN}export PATH=\"$BIN_DIR:\$PATH\"${NC}"
    fi
else
    warn "Could not find a writable bin directory."
    warn "Run pyoz directly with: $LAUNCHER"
fi

# ── Verify ────────────────────────────────────────────────────
echo ""
ok "PyOz installed successfully!"
echo ""
info "Quick start:"
echo "  pyoz --provider claude --api-key YOUR_KEY"
echo "  pyoz --provider openai --api-key YOUR_KEY"
echo "  pyoz --provider ollama --model qwen2.5:7b"
echo "  pyoz --test                    # Run self-test"
echo ""
info "Set API key as env var to skip --api-key flag:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  export OPENAI_API_KEY=sk-..."
echo ""
