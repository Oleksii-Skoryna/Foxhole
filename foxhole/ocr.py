import logging
import re
from difflib import get_close_matches
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytesseract
from PIL import ImageGrab
from pytesseract import Output

from .config import cfg

_TEMPLATE_PATH = Path(__file__).parent.parent / "data" / "activity_log.png"
_template: np.ndarray | None = None

_TESS_BLOCK  = "--oem 3 --psm 6"
_TESS_SPARSE = "--oem 3 --psm 6 -c load_system_dawg=0 -c load_freq_dawg=0"

logger = logging.getLogger(__name__)


def _save_debug(img: np.ndarray, name: str) -> None:
    cfg.paths.debug.mkdir(exist_ok=True)
    cv2.imwrite(str(cfg.paths.debug / f"{name}.png"), img)


def _grab_crop_invert(bbox: tuple[int, int, int, int]) -> np.ndarray:
    img = ImageGrab.grab(bbox=bbox)
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    return cv2.bitwise_not(gray)


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


def _get_template() -> np.ndarray:
    global _template
    if _template is None:
        _template = cv2.imread(str(_TEMPLATE_PATH))
        if _template is None:
            raise FileNotFoundError(f"Activity Log template not found: {_TEMPLATE_PATH}")
    return _template


def save_screenshot(name: str) -> None:
    """Grab the full screen and save it to the debug folder as <name>.png."""
    screenshot = ImageGrab.grab()
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    _save_debug(img, name)


def find_activity_log_button(click_x: int, click_y: int) -> tuple[int, int] | None:
    """Template-match the Activity Log button in a region around the player click point."""
    template = _get_template()
    th, tw = template.shape[:2]

    o = cfg.ocr
    bbox = (click_x, click_y, click_x + o.context_menu_search_w, click_y + o.context_menu_search_h)
    crop_pil = ImageGrab.grab(bbox=bbox)
    crop = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
    _save_debug(crop, "grab_context_menu_search")

    result = cv2.matchTemplate(crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < o.button_match_threshold:
        logger.warning(f"Activity Log button not found (confidence {max_val:.2f})")
        return None

    cx = click_x + max_loc[0] + tw // 2
    cy = click_y + max_loc[1] + th // 2
    logger.debug(f"Activity Log button at ({cx}, {cy}), confidence={max_val:.2f}")
    return cx, cy


def get_regiment_member_count() -> int | None:
    """OCR the member count shown in the regiment screen header."""
    s = cfg.screen
    bbox = (s.member_count_crop_x1, s.member_count_crop_y1,
            s.member_count_crop_x2, s.member_count_crop_y2)
    inverted = _grab_crop_invert(bbox)
    _save_debug(inverted, "grab_member_count")

    try:
        text = pytesseract.image_to_string(inverted, config=_TESS_SPARSE)
    except Exception as e:
        logger.error(f"Tesseract failed reading member count: {e}")
        return None

    match = re.search(r'\d+', text)
    if match:
        count = int(match.group())
        logger.info(f"Regiment member count: {count}")
        return count

    logger.warning(f"Could not parse member count from: '{text.strip()}'")
    return None


def get_visible_players() -> list[dict]:
    """Return all players visible in the name list as dicts with 'name' and 'screen_y'."""
    logger.debug("OCR-ing visible player names...")
    s = cfg.screen
    bbox = (s.name_crop_x1, s.name_crop_y1, s.name_crop_x2, s.name_crop_y2)
    inverted = _grab_crop_invert(bbox)
    inverted = cv2.copyMakeBorder(
        inverted, 0, 0, cfg.ocr.name_crop_padding, cfg.ocr.name_crop_padding, cv2.BORDER_REPLICATE
    )
    _save_debug(inverted, "grab_name_scan")

    try:
        data = pytesseract.image_to_data(inverted, config=_TESS_SPARSE, output_type=Output.DICT)
    except Exception as e:
        logger.error(f"Tesseract failed during name scan: {e}")
        return []

    df = pd.DataFrame(data)
    df = df[(df["conf"] > cfg.ocr.name_conf_threshold) & (df["text"].str.strip() != "")]

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


def ocr_activity_log(player_name: str) -> dict:
    """OCR the activity log panel and return a dict mapping stat keys to integer values."""
    logger.debug(f"OCR-ing activity log for '{player_name}'...")
    s = cfg.screen
    bbox = (s.log_crop_x1, s.log_crop_y1, s.log_crop_x2, s.log_crop_y2)
    crop_pil = ImageGrab.grab(bbox=bbox)
    crop = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)

    processed = _preprocess(crop)
    _save_debug(crop, "grab_activity_log_crop")
    _save_debug(processed, "grab_activity_log_processed")

    try:
        text = pytesseract.image_to_string(processed, config=_TESS_BLOCK)
    except Exception as e:
        logger.error(f"Tesseract failed for '{player_name}': {e}")
        return {k: None for k in cfg.ocr.expected_keys}

    parsed = _parse_log_text(text)
    result = {k: parsed.get(k) for k in cfg.ocr.expected_keys}

    missing = [k for k, v in result.items() if v is None]
    if missing:
        logger.warning(f"'{player_name}' — {len(missing)}/{len(cfg.ocr.expected_keys)} fields missing: {missing}")
    else:
        logger.debug(f"All {len(cfg.ocr.expected_keys)} fields captured for '{player_name}'.")

    return result
