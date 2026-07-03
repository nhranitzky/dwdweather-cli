# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "platformdirs>=4.0",
#   "rich>=13.0",
#   "typer>=0.12",
# ]
# ///

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dwdweather.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
