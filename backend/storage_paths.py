import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("VOICEMEDIC_DATA_DIR") or BASE_DIR / "data").expanduser()
