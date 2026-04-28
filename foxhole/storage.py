import logging
import os
from difflib import get_close_matches

import pandas as pd

from .config import cfg

logger = logging.getLogger(__name__)


def load_seen_names(csv_path: str) -> tuple[set, set]:
    if not os.path.exists(csv_path):
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


def append_to_csv(record: dict, csv_path: str, overwrite_name: str = None) -> None:
    if overwrite_name and os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df = df[df["player_name"] != overwrite_name]
        df.to_csv(csv_path, index=False)
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=False, index=False)
        logger.debug(f"Overwrote row for '{record['player_name']}'.")
    else:
        write_header = not os.path.exists(csv_path)
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=write_header, index=False)
        logger.debug(f"Appended '{record['player_name']}'.")
