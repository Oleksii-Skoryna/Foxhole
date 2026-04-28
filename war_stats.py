import pyautogui
import pytesseract
from pytesseract import Output
import pandas as pd
from PIL import ImageGrab
import cv2
import numpy as np
import re
import time
import logging
from difflib import get_close_matches
import pygetwindow as gw
from datetime import datetime

# ----------------------------
# LOGGING SETUP
# ----------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
log = logging.getLogger(__name__)


# ----------------------------
# CALIBRATION CONSTANTS
# ----------------------------
NAME_CROP_X1 = 940      # name column left edge (absolute screen coords)
NAME_CROP_Y1 = 335      # name column top edge
NAME_CROP_X2 = 1145      # name column right edge
NAME_CROP_Y2 = 675      # name column bottom edge

MENU_OFFSET_X = 32     # x offset from click point to Activity Log menu item
MENU_OFFSET_Y = 42     # y offset from click point to Activity Log menu item

# Activity log panel crop (your existing coords from war_stats.py)
LOG_CROP_X1 = 660
LOG_CROP_Y1 = 125
LOG_CROP_X2 = 1250
LOG_CROP_Y2 = 650

MOVE_DURATION = 0.2         # seconds for all mouse movements
SCROLLS_PER_PAGE = 1320     # scroll notches for one full regiment screen


EXPECTED_KEYS = [
    "Enemy Player Damage",
    "Friendly Player Damage",
    "Enemy Structure/Vehicle Damage",
    "Friendly Structure/Vehicle Damage",
    "Friendly Construction",
    "Friendly Repairing",
    "Friendly Healing",
    "Friendly Revivals",
    "Vehicles Captured By Enemy",
    "Vehicle Self Damage (Neutral)",
    "Vehicle Self Damage (Colonial)",
    "Vehicle Self Damage (Warden)",
    "Materials Submitted",
    "Materials Gathered",
    "Supply Value Delivered"
]


# ----------------------------
# MOUSE HELPERS
# ----------------------------
def smooth_click(x, y):
    log.debug(f"Clicking ({x}, {y})")
    pyautogui.moveTo(x, y, duration=MOVE_DURATION)
    pyautogui.click()


def smooth_move(x, y):
    log.debug(f"Moving to ({x}, {y})")
    pyautogui.moveTo(x, y, duration=MOVE_DURATION)


# ----------------------------
# SCROLL HELPERS
# ----------------------------
def scroll_to_page(page: int):
    """After reopening regiment screen, scroll back down to the current page."""
    if page == 0:
        return
    total_scrolls = page * SCROLLS_PER_PAGE
    log.info(f"Restoring scroll position to page {page} ({total_scrolls} notches)...")
    cx = (NAME_CROP_X1 + NAME_CROP_X2) // 2
    cy = (NAME_CROP_Y1 + NAME_CROP_Y2) // 2
    smooth_move(cx, cy)
    pyautogui.scroll(-total_scrolls)
    time.sleep(0.3)
    log.info("Scroll position restored.")


def scroll_down_one_page():
    log.debug(f"Scrolling down one page ({SCROLLS_PER_PAGE} notches)...")
    cx = (NAME_CROP_X1 + NAME_CROP_X2) // 2
    cy = (NAME_CROP_Y1 + NAME_CROP_Y2) // 2
    smooth_move(cx, cy)
    pyautogui.scroll(-SCROLLS_PER_PAGE)
    time.sleep(0.3)


# ----------------------------
# REGIMENT SCREEN HELPERS
# ----------------------------
def open_regiment_screen():
    log.debug("Opening regiment screen (F1)...")
    pyautogui.press("f1")
    time.sleep(0.5)


def close_activity_log():
    log.debug("Closing activity log (Escape) and reopening regiment screen (F1)...")
    pyautogui.press("escape")
    time.sleep(0.3)
    open_regiment_screen()


# ----------------------------
# NAME SCRAPING
# ----------------------------
def get_visible_players() -> list[dict]:
    log.debug("Screenshotting and OCR-ing visible player names...")
    screenshot = ImageGrab.grab()
    crop = screenshot.crop((NAME_CROP_X1, NAME_CROP_Y1, NAME_CROP_X2, NAME_CROP_Y2))

    crop_cv = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(crop_cv, cv2.COLOR_BGR2GRAY)
    inverted = cv2.bitwise_not(gray)

    data = pytesseract.image_to_data(
        inverted,
        config="--oem 3 --psm 6",
        output_type=Output.DICT
    )

    df = pd.DataFrame(data)
    df = df[df["conf"] > 0]
    df = df[df["text"].str.strip() != ""]

    players = []
    for (par, line), group in df.groupby(["par_num", "line_num"]):
        name = " ".join(group["text"].tolist()).strip()
        if not name:
            continue
        top_in_crop = group["top"].iloc[0]
        height_in_crop = group["height"].iloc[0]
        screen_y = NAME_CROP_Y1 + top_in_crop + height_in_crop // 2
        players.append({"name": name, "screen_y": screen_y})

    log.debug(f"Detected {len(players)} visible players: {[p['name'] for p in players]}")
    return players


# ----------------------------
# ACTIVITY LOG OCR
# ----------------------------
def preprocess(image, debug=False):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if debug:
        cv2.imwrite("debug_1_gray.png", gray)

    gray = cv2.convertScaleAbs(gray, alpha=1, beta=0)
    if debug:
        cv2.imwrite("debug_2_contrast.png", gray)

    inverted = cv2.bitwise_not(gray)
    if debug:
        cv2.imwrite("debug_3_inverted.png", inverted)

    return inverted


def normalize_key(key):
    match = get_close_matches(key, EXPECTED_KEYS, n=1, cutoff=0.7)
    return match[0] if match else key


def parse_text(text):
    pattern = r'([A-Za-z\s\/\(\)]+):\s*([\d,]+)'
    matches = re.findall(pattern, text)
    data = {}
    for key, value in matches:
        key = normalize_key(key.strip())
        value = int(value.replace(",", ""))
        data[key] = value
    return data


def ocr_activity_log(player_name: str, debug=False) -> dict:
    """
    Always returns a full dict with all EXPECTED_KEYS.
    Missing fields are set to None with a warning logged.
    """
    log.debug(f"OCR-ing activity log for '{player_name}'...")
    screenshot = ImageGrab.grab()
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    crop = img[LOG_CROP_Y1:LOG_CROP_Y2, LOG_CROP_X1:LOG_CROP_X2]

    processed = preprocess(crop, debug=debug)
    config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(processed, config=config)

    if debug:
        log.debug(f"Raw OCR output for '{player_name}':\n{text}")

    parsed = parse_text(text)

    # Build result with None for any missing fields
    result = {}
    missing = []
    for key in EXPECTED_KEYS:
        if key in parsed:
            result[key] = parsed[key]
        else:
            result[key] = None
            missing.append(key)

    if missing:
        log.warning(f"  ⚠ '{player_name}' — {len(missing)} field(s) not detected, set to null:")
        for m in missing:
            log.warning(f"      - {m}")
    else:
        log.debug(f"  All 15 fields captured for '{player_name}'.")

    return result


# ----------------------------
# MAIN LOOP
# ----------------------------
def scrape_regiment() -> pd.DataFrame:
    log.info("Focusing Foxhole window...")
    windows = gw.getWindowsWithTitle("War")
    if not windows:
        log.error("Foxhole (War.exe) not found. Make sure the game is running.")
        return pd.DataFrame()
    windows[0].activate()
    time.sleep(1)
    log.info("Foxhole window focused.")

    records = []
    seen_names = set()
    partial_names = []
    page = 0

    while True:
        log.info(f"=== Page {page} ===")

        players = get_visible_players()
        new_players = [p for p in players if p["name"] not in seen_names]

        if not new_players:
            log.info("No new players detected. End of regiment list reached.")
            break

        log.info(f"{len(new_players)} new players on this page.")

        for player in new_players:
            name = player["name"]
            click_y = player["screen_y"] - 5
            click_x = (NAME_CROP_X1 + NAME_CROP_X2) // 2

            log.info(f"[{len(seen_names) + 1}] Processing: '{name}' at y={click_y}")

            # Open submenu
            smooth_click(click_x, click_y)
            time.sleep(0.4)

            # Click Activity Log
            smooth_click(click_x + MENU_OFFSET_X, click_y + MENU_OFFSET_Y)
            time.sleep(1.2)

            # OCR — always returns full dict, nulls for missing fields
            log_data = ocr_activity_log(name)
            log_data["player_name"] = name

            null_count = sum(1 for v in log_data.values() if v is None)
            if null_count > 0:
                partial_names.append((name, null_count))
                log.warning(f"  ✓ (partial) '{name}' saved with {null_count} null field(s).")
            else:
                log.info(f"  ✓ '{name}' fully captured.")

            records.append(log_data)
            seen_names.add(name)

            # Close log, reopen regiment screen, restore scroll position
            close_activity_log()
            # scroll_to_page(page)

        # Advance to next page
        log.info(f"Page {page} complete. Scrolling to page {page + 1}...")
        scroll_down_one_page()
        page += 1

    # ----------------------------
    # SUMMARY
    # ----------------------------
    log.info("=" * 40)
    log.info("Scrape complete.")
    log.info(f"  Total processed : {len(seen_names)}")
    log.info(f"  Fully captured  : {len(records) - len(partial_names)}")
    log.info(f"  Partial (nulls) : {len(partial_names)}")
    if partial_names:
        log.warning("  Partial players:")
        for name, count in partial_names:
            log.warning(f"    - {name}: {count} null field(s)")

    df = pd.DataFrame(records)
    output_file = f"regiment_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)
    log.info(f"Saved to {output_file}")

    return df


# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == "__main__":
    log.info("Starting in 5 seconds, switch to Foxhole and open the regiment screen manually...")
    time.sleep(5)
    scrape_regiment()