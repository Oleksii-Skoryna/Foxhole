import logging
from pathlib import Path

import pandas as pd
from difflib import get_close_matches

from .config import cfg

logger = logging.getLogger(__name__)


def load_seen_names(csv_path: Path) -> tuple[set, set]:
    """Load player names from CSV, returning (complete, needs_rescan) name sets."""
    if not csv_path.exists():
        logger.info(f"No existing CSV at '{csv_path}', starting fresh.")
        return set(), set()

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.warning(f"Failed to read '{csv_path}' ({e}), starting fresh.")
        return set(), set()

    if "player_name" not in df.columns:
        logger.warning("CSV has no 'player_name' column, starting fresh.")
        return set(), set()

    all_names = set(df["player_name"].dropna())
    rescan_names = set(df[df.isnull().any(axis=1)]["player_name"].dropna())
    complete_names = all_names - rescan_names

    logger.info(f"Loaded {len(all_names)} players from '{csv_path}'.")
    if rescan_names:
        logger.info(f"  {len(complete_names)} complete, {len(rescan_names)} flagged for rescan.")
    return complete_names, rescan_names


def is_already_seen(name: str, seen_names: set, rescan_names: set, all_seen: set = None) -> bool:
    """Return True if name fuzzy-matches a complete record; False if unseen or flagged for rescan."""
    candidates = all_seen if all_seen is not None else seen_names | rescan_names
    match = get_close_matches(name, candidates, n=1, cutoff=cfg.ocr.name_match_cutoff)
    if not match:
        return False
    matched = match[0]
    if matched in rescan_names:
        logger.debug(f"'{name}' matched '{matched}' (has nulls) — will rescan.")
        return False
    logger.debug(f"'{name}' matched complete record '{matched}' — skipping.")
    return True


def append_to_csv(record: dict, csv_path: Path, overwrite_name: str = None) -> None:
    """Append record to CSV, replacing the existing row if overwrite_name is given."""
    if overwrite_name and csv_path.exists():
        df = pd.read_csv(csv_path)
        df = df[df["player_name"] != overwrite_name]
        df.to_csv(csv_path, index=False)
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=False, index=False)
        logger.debug(f"Overwrote row for '{record['player_name']}'.")
    else:
        write_header = not csv_path.exists()
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=write_header, index=False)
        logger.debug(f"Appended '{record['player_name']}'.")
