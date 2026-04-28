import pyautogui
import pytesseract
from pytesseract import Output
import pandas as pd
from PIL import ImageGrab, ImageOps
import cv2
import numpy as np
import re
import time
from difflib import get_close_matches
import pygetwindow as gw


# ----------------------------
# CALIBRATION CONSTANTS
# ----------------------------
NAME_CROP_X1 = 940      # name column left edge (absolute screen coords)
NAME_CROP_Y1 = 335      # name column top edge
NAME_CROP_X2 = 1145      # name column right edge
NAME_CROP_Y2 = 675      # name column bottom edge

MENU_OFFSET_X = 35     # x offset from click point to Activity Log menu item
MENU_OFFSET_Y = 45     # y offset from click point to Activity Log menu item

# Activity log panel crop (your existing coords from war_stats.py)
LOG_CROP_X1 = 660
LOG_CROP_Y1 = 125
LOG_CROP_X2 = 1250
LOG_CROP_Y2 = 650

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
# SCROLL HELPERS
# ----------------------------
def scroll_to_top():
    pyautogui.moveTo((NAME_CROP_X1 + NAME_CROP_X2) // 2, (NAME_CROP_Y1 + NAME_CROP_Y2) // 2)
    for _ in range(11 * 40):
        pyautogui.scroll(1)
    time.sleep(0.5)


def scroll_down_one_page():
    pyautogui.moveTo((NAME_CROP_X1 + NAME_CROP_X2) // 2, (NAME_CROP_Y1 + NAME_CROP_Y2) // 2)
    for _ in range(11):
        pyautogui.scroll(-1)
        time.sleep(0.05)
    time.sleep(0.3)


# ----------------------------
# NAME SCRAPING
# ----------------------------
def get_visible_players() -> list[dict]:
    screenshot = ImageGrab.grab()
    crop = screenshot.crop((NAME_CROP_X1, NAME_CROP_Y1, NAME_CROP_X2, NAME_CROP_Y2))
    crop = ImageOps.invert(crop.convert("RGB"))

    data = pytesseract.image_to_data(
        crop,
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

    return players


# ----------------------------
# ACTIVITY LOG OCR (your existing pipeline, adapted for live screenshot)
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


def validate(data):
    if len(data) != 15:
        raise ValueError(f"Expected 15 fields, got {len(data)}")


def ocr_activity_log(debug=False) -> dict | None:
    # Grab live screenshot and crop the log panel
    screenshot = ImageGrab.grab()
    # Convert PIL to OpenCV format
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    crop = img[LOG_CROP_Y1:LOG_CROP_Y2, LOG_CROP_X1:LOG_CROP_X2]

    processed = preprocess(crop, debug=debug)

    config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(processed, config=config)

    if debug:
        print("\n--- OCR RAW OUTPUT ---\n")
        print(text)

    data = parse_text(text)

    try:
        validate(data)
    except ValueError as e:
        print(f"  ⚠️ Validation error: {e}")
        return None

    return data


# ----------------------------
# MAIN LOOP
# ----------------------------
def scrape_regiment() -> pd.DataFrame:
    # Focus Foxhole
    windows = gw.getWindowsWithTitle("War")
    if not windows:
        print("Foxhole (War.exe) not found, make sure the game is running.")
        return pd.DataFrame()
    windows[0].activate()
    time.sleep(1)

    records = []
    seen_names = set()

    # scroll_to_top()

    while True:
        players = get_visible_players()

        new_players = [p for p in players if p["name"] not in seen_names]
        if not new_players:
            print("No new players found, end of list reached.")
            break

        for player in new_players:
            name = player["name"]
            click_y = player["screen_y"]
            click_x = (NAME_CROP_X1 + NAME_CROP_X2) // 2

            print(f"Processing: {name} at y={click_y}")

            # Open submenu
            pyautogui.moveTo(click_x, click_y)
            time.sleep(1)
            pyautogui.click()
            time.sleep(1)

            # Click Activity Log
            pyautogui.click(click_x + MENU_OFFSET_X, click_y + MENU_OFFSET_Y)
            time.sleep(1)

            # OCR the log
            log_data = ocr_activity_log()

            if log_data is not None:
                log_data["player_name"] = name
                records.append(log_data)
            else:
                print(f"  ⚠️ Skipping {name} due to OCR failure.")

            seen_names.add(name)

            # Close log
            pyautogui.press("escape")
            time.sleep(1)
            pyautogui.press("f1")

        scroll_down_one_page()

    df = pd.DataFrame(records)
    df.to_csv("regiment_activity.csv", index=False)
    print(f"Done. {len(df)} players scraped.")
    return df


if __name__ == "__main__":
    print("Starting in 5 seconds, switch to Foxhole...")
    time.sleep(5)
    scrape_regiment()