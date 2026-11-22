"""Load the labelled sets in one standard shape."""
import hashlib
from pathlib import Path

import pandas as pd

from zenai.config import DATA

SET_FILES = {"dev": "dev_set.csv", "test": "test_set.csv", "simulated": "simulated_synced.csv"}
TEST_SETS = {"test", "simulated"}


def read_csv(path: Path) -> pd.DataFrame:
    # utf-8-sig strips the BOM Excel writes; empty cells stay "" rather than NaN
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def load_set(name: str) -> pd.DataFrame:
    """Columns: id, question, language, source, variant_type, label_primary, label_secondary, label_action."""
    df = read_csv(DATA / SET_FILES[name])
    return pd.DataFrame({
        "id": df["id"],
        "question": df["question"],
        "language": df["language"],
        "source": df["source"],
        "variant_type": df["variant_type"] if "variant_type" in df else "",
        "label_primary": df["primary_domain"],
        "label_secondary": df["secondary_domain"],
        "label_action": df["expected_action"],
    })


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
