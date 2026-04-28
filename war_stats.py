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
import os
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
NAME_CROP_X1 = 945
NAME_CROP_Y1 = 335
NAME_CROP_X2 = 1145
NAME_CROP_Y2 = 675

MENU_OFFSET_X = 32
MENU_OFFSET_Y = 42

LOG_CROP_X1 = 660
LOG_CROP_Y1 = 125
LOG_CROP_X2 = 1250
LOG_CROP_Y2 = 650

MOVE_DURATION = 0.2
SCROLLS_PER_PAGE = 1314

# Fixed output file — same file every run so resume works
OUTPUT_CSV = "regiment_activity.csv"

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
# CSV HELPERS
# ----------------------------
def load_seen_names(csv_path: str) -> tuple[set, set]:
    """
    Load already-processed player names from existing CSV.
    Returns (seen_names, partial_names) where partial_names are
    players with any None values that should be rescanned.
    """
    if not os.path.exists(csv_path):
        log.info(f"No existing CSV found at '{csv_path}', starting fresh.")
        return set(), set()
    df = pd.read_csv(csv_path)
    if "player_name" not in df.columns:
        log.warning("CSV exists but has no 'player_name' column, starting fresh.")
        return set(), set()
    all_names = set(df["player_name"].dropna().tolist())
    # Players with any None/NaN fields need to be rescanned
    has_nulls = df[df.isnull().any(axis=1)]["player_name"].dropna().tolist()
    rescan_names = set(has_nulls)
    complete_names = all_names - rescan_names
    log.info(f"Loaded {len(all_names)} players from '{csv_path}'.")
    if rescan_names:
        log.info(f"  {len(complete_names)} complete, {len(rescan_names)} will be rescanned (have nulls).")
    return complete_names, rescan_names


# ----------------------------
# FUZZY NAME MATCHING
# ----------------------------
NAME_MATCH_CUTOFF = 0.85  # tune lower if too strict, higher if too lenient

def is_already_seen(name: str, seen_names: set, rescan_names: set) -> bool:
    """
    Returns True only if name fuzzy-matches a COMPLETE (no nulls) record.
    Players in rescan_names are not skipped — they need to be reprocessed.
    """
    match = get_close_matches(name, seen_names | rescan_names, n=1, cutoff=NAME_MATCH_CUTOFF)
    if not match:
        return False
    matched = match[0]
    if matched in rescan_names:
        log.debug(f"'{name}' matched '{matched}' which has nulls — will rescan.")
        return False
    log.debug(f"'{name}' matched complete record '{matched}' — skipping.")
    return True


def append_to_csv(record: dict, csv_path: str, overwrite_name: str = None):
    """
    Append a single record to CSV.
    If overwrite_name is set, removes the existing row for that player first.
    """
    if overwrite_name and os.path.exists(csv_path):
        existing = pd.read_csv(csv_path)
        existing = existing[existing["player_name"] != overwrite_name]
        existing.to_csv(csv_path, index=False)
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=False, index=False)
        log.debug(f"Overwrote existing row for '{record['player_name']}' in CSV.")
    else:
        write_header = not os.path.exists(csv_path)
        pd.DataFrame([record]).to_csv(csv_path, mode="a", header=write_header, index=False)
        log.debug(f"Written '{record['player_name']}' to CSV.")


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
    # Move mouse away from the log panel so it doesn't appear in the screenshot
    screenshot = ImageGrab.grab()
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    crop = img[LOG_CROP_Y1:LOG_CROP_Y2, LOG_CROP_X1:LOG_CROP_X2]

    processed = preprocess(crop, debug=debug)
    config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(processed, config=config)

    if debug:
        log.debug(f"Raw OCR output for '{player_name}':\n{text}")

    parsed = parse_text(text)

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
def scrape_regiment():
    log.info("Focusing Foxhole window...")
    windows = gw.getWindowsWithTitle("War")
    if not windows:
        log.error("Foxhole (War.exe) not found. Make sure the game is running.")
        return
    windows[0].activate()
    time.sleep(1)
    log.info("Foxhole window focused.")

    # Load already-processed names from CSV to allow resuming
    seen_names, rescan_names = load_seen_names(OUTPUT_CSV)

    partial_names = []
    total_written = 0
    page = 0

    while True:
        log.info(f"=== Page {page} ===")

        players = get_visible_players()
        new_players = [p for p in players if not is_already_seen(p["name"], seen_names, rescan_names)]

        if not new_players:
            log.info("No new players detected on this page, scrolling down...")
            scroll_down_one_page()
            page += 1
            continue

        skipped = len(players) - len(new_players)
        if skipped:
            log.info(f"Skipping {skipped} already-processed player(s) on this page.")
        log.info(f"{len(new_players)} new players to process on this page.")

        for player in new_players:
            name = player["name"]
            click_y = player["screen_y"] - 6
            click_x = (NAME_CROP_X1 + NAME_CROP_X2) // 2

            log.info(f"[{len(seen_names) + 1}] Processing: '{name}' at y={click_y}")

            # Open submenu
            smooth_click(click_x, click_y)
            time.sleep(0.4)

            # Click Activity Log
            smooth_click(click_x + MENU_OFFSET_X, click_y + MENU_OFFSET_Y)
            pyautogui.moveTo(NAME_CROP_X1, NAME_CROP_Y2 + 200, duration=MOVE_DURATION)
            time.sleep(1.2)

            # First OCR attempt
            log_data = ocr_activity_log(name)

            null_count = sum(1 for v in log_data.values() if v is None)
            if null_count > 0:
                log.warning(f"  {null_count} null(s) on first attempt for '{name}', rescanning...")
                time.sleep(0.5)
                retry_data = ocr_activity_log(name)
                retry_nulls = sum(1 for v in retry_data.values() if v is None)

                # Use whichever attempt got more fields
                if retry_nulls < null_count:
                    log.info(f"  Rescan improved: {null_count} -> {retry_nulls} null(s).")
                    log_data = retry_data
                    null_count = retry_nulls
                else:
                    log.warning(f"  Rescan did not improve ({retry_nulls} null(s)), keeping first result.")

            log_data["player_name"] = name

            if null_count > 0:
                partial_names.append((name, null_count))
                log.warning(f"  ✓ (partial) '{name}' saved with {null_count} null field(s).")
            else:
                log.info(f"  ✓ '{name}' fully captured.")

            # Write immediately to CSV, overwriting if this was a rescan
            is_rescan = is_already_seen(name, set(), rescan_names) == False and name in rescan_names
            append_to_csv(log_data, OUTPUT_CSV, overwrite_name=name if is_rescan else None)
            seen_names.add(name)
            rescan_names.discard(name)
            total_written += 1

            # Close log and reopen regiment screen
            close_activity_log()

        # Advance to next page
        log.info(f"Page {page} complete. Scrolling to page {page + 1}...")
        scroll_down_one_page()
        page += 1

    # ----------------------------
    # SUMMARY
    # ----------------------------
    log.info("=" * 40)
    log.info("Scrape complete.")
    log.info(f"  Written this run : {total_written}")
    log.info(f"  Total in CSV     : {len(seen_names)}")
    log.info(f"  Partial (nulls)  : {len(partial_names)}")
    if partial_names:
        log.warning("  Partial players:")
        for name, count in partial_names:
            log.warning(f"    - {name}: {count} null field(s)")
    log.info(f"  Output file      : {OUTPUT_CSV}")


# ----------------------------
# ENTRY POINT
# ----------------------------
if __name__ == "__main__":
    log.info("Starting in 5 seconds, switch to Foxhole and open the regiment screen manually...")
    time.sleep(5)
    scrape_regiment()