import sys
from pathlib import Path

# Put the project root on sys.path so `from ops import agent, sweep`
# (ops/__init__.py then finds turphOps' ops_core)
# works when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
