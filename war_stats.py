from PIL import Image
import pytesseract
import cv2
import re
from cv2.gapi import crop
from difflib import get_close_matches
import pandas as pd

pattern = r'([A-Za-z\s\/]+):\s*([\d,]+)'
custom_config = r'--oem 3 --psm 6'

expected_keys = [
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

def normalize_key(k):
    match = get_close_matches(k, expected_keys, n=1, cutoff=0.7)
    return match[0] if match else k

gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

# Increase contrast
gray = cv2.convertScaleAbs(gray, alpha=2, beta=0)

# Threshold (experiment with these)
thresh = cv2.adaptiveThreshold(
    gray, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    11, 2
)

# Optional: denoise
thresh = cv2.medianBlur(thresh, 3)

text = pytesseract.image_to_string(thresh, config=custom_config)

matches = re.findall(pattern, text)

data = {}
for key, value in matches:
    clean_key = key.strip()
    clean_value = int(value.replace(",", ""))
    data[clean_key] = clean_value