import logging
import re
from difflib import get_close_matches

import cv2
import numpy as np
import pandas as pd
import pytesseract
from PIL import ImageGrab
from pytesseract import Output

from .config import cfg

logger = logging.getLogger(__name__)


def _preprocess(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.bitwise_not(gray)


def _normalize_key(key: str) -> str:
    match = get_close_matches(key, cfg.ocr.expected_keys, n=1, cutoff=cfg.ocr.key_match_cutoff)
    if not match:
        logger.debug(f"No key match for OCR token: '{key}'")
        return key
    return match[0]


def _parse_log_text(text: str) -> dict:
    result = {}
    for k, v in re.findall(r'([A-Za-z \t\/\(\)]+):\s*([\d,]+)', text):
        normalized = _normalize_key(k.strip())
        if normalized not in result:
            result[normalized] = int(v.replace(",", ""))
    return result


def get_visible_players() -> list[dict]:
    logger.debug("OCR-ing visible player names...")
    s = cfg.screen
    screenshot = ImageGrab.grab()
    crop = screenshot.crop((s.name_crop_x1, s.name_crop_y1, s.name_crop_x2, s.name_crop_y2))

    gray = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2GRAY)
    inverted = cv2.bitwise_not(gray)
    inverted = cv2.copyMakeBorder(
        inverted, 0, 0, cfg.ocr.name_crop_padding, cfg.ocr.name_crop_padding, cv2.BORDER_REPLICATE
    )

    try:
        data = pytesseract.image_to_data(
            inverted,
            config="--oem 3 --psm 6 -c load_system_dawg=0 -c load_freq_dawg=0",
            output_type=Output.DICT,
        )
    except Exception as e:
        logger.error(f"Tesseract failed during name scan: {e}")
        return []

    df = pd.DataFrame(data)
    df = df[(df["conf"] > 30) & (df["text"].str.strip() != "")]

    players = []
    for (par_num, line_num), group in df.groupby(["par_num", "line_num"]):
        name = " ".join(group["text"].tolist()).strip().lstrip(" )}")
        if not name:
            continue
        top = group["top"].iloc[0]
        height = group["height"].iloc[0]
        players.append({"name": name, "screen_y": s.name_crop_y1 + top + height // 2})

    logger.debug(f"Detected {len(players)} players: {[p['name'] for p in players]}")
    return players


def ocr_activity_log(player_name: str, debug: bool = False) -> dict:
    logger.debug(f"OCR-ing activity log for '{player_name}'...")
    s = cfg.screen
    screenshot = ImageGrab.grab()
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    crop = img[s.log_crop_y1:s.log_crop_y2, s.log_crop_x1:s.log_crop_x2]

    processed = _preprocess(crop)
    if debug:
        cfg.paths.debug.mkdir(exist_ok=True)
        cv2.imwrite(str(cfg.paths.debug / "debug_1_gray.png"), cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
        cv2.imwrite(str(cfg.paths.debug / "debug_3_inverted.png"), processed)

    try:
        text = pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
    except Exception as e:
        logger.error(f"Tesseract failed for '{player_name}': {e}")
        return {k: None for k in cfg.ocr.expected_keys}

    if debug:
        logger.debug(f"Raw OCR for '{player_name}':\n{text}")

    parsed = _parse_log_text(text)
    result = {k: parsed.get(k) for k in cfg.ocr.expected_keys}

    missing = [k for k, v in result.items() if v is None]
    if missing:
        logger.warning(f"'{player_name}' — {len(missing)}/{len(cfg.ocr.expected_keys)} fields missing: {missing}")
    else:
        logger.debug(f"All {len(cfg.ocr.expected_keys)} fields captured for '{player_name}'.")

    return result
