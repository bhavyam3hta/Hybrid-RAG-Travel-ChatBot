#!/bin/zsh
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
[[ -f config.py ]] || cp config.example.py config.py
.venv/bin/python app.py
read "?Press Enter to close..."
