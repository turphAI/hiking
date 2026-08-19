import sys
from pathlib import Path

# Put the project root on sys.path so `from ops import contract, agent, sweep`
# works when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
