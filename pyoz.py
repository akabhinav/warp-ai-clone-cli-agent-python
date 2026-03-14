#!/usr/bin/env python3
"""PyOz — Pure Agent Mode Coding Assistant.

Usage:
  python pyoz.py --provider claude --api-key sk-ant-...
  python pyoz.py --provider openai --api-key sk-...
  python pyoz.py --provider ollama --model qwen2.5:7b
  python pyoz.py --test
"""

from pyoz.cli import main

if __name__ == "__main__":
    main()
