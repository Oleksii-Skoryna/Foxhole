import cv2
import pytesseract
import pandas as pd
import re
from difflib import get_close_matches


# -----------------------------
# 1. CONFIG
# -----------------------------

CROP_X1 = 660
CROP_Y1 = 125
CROP_X2 = 1250
CROP_Y2 = 650

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


# -----------------------------
# 2. OCR PIPELINE
# -----------------------------

def preprocess(image, debug=False):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if debug:
        cv2.imwrite("debug_1_gray.png", gray)

    gray = cv2.convertScaleAbs(gray, alpha=1, beta=0)

    if debug:
        cv2.imwrite("debug_2_contrast.png", gray)

    return gray

def run_ocr(image):
    config = r'--oem 3 --psm 6'
    return pytesseract.image_to_string(image, config=config)


# -----------------------------
# 3. PARSING
# -----------------------------

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


# -----------------------------
# 4. VALIDATION
# -----------------------------

def validate(data):
    if len(data) != 15:
        raise ValueError(f"Expected 15 fields, got {len(data)}")


# -----------------------------
# 5. MAIN FUNCTION
# -----------------------------

def extract_stats(image_path):
    try:
        img = cv2.imread(image_path)

        if img is None:
            raise ValueError("Image not found")

        # Crop
        crop = img[CROP_Y1:CROP_Y2, CROP_X1:CROP_X2]

        # Preprocess
        processed = preprocess(crop, debug=True)

        # OCR
        text = run_ocr(processed)

        print("\n--- OCR RAW OUTPUT ---\n")
        print(text)

        # Parse
        data = parse_text(text)

        # Validate (raises if bad)
        validate(data)

        # DataFrame
        df = pd.DataFrame([data])

        return df

    except ValueError as e:
        print(f"⚠️ Validation error: {e}")
        return None


# -----------------------------
# 6. RUN
# -----------------------------

if __name__ == "__main__":
    df = extract_stats("data/Unedited.jpg")

    if df is not None:
        print("\n--- DATAFRAME ---\n")
        print(df)