import os
from pathlib import Path

# Data directory — the peaks/hikes DB lives here, gitignored.
DATA_DIR = Path(os.environ.get("HIKING_DATA_DIR", Path(__file__).parent.parent / "data"))
DB_PATH = DATA_DIR / "hiking.db"
