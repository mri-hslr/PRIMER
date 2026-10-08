from __future__ import annotations

import csv
from typing import List

from config import DATA_FILE


def load_interactions() -> List[dict]:
    """Read the full historical interactions CSV."""
    with DATA_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))