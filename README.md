# Foxhole Regiment Scraper

Automatically scrapes activity log stats for every member of your regiment and saves them to a CSV.

## Requirements

- **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- **Tesseract OCR**
  - Windows: [download installer](https://github.com/UB-Mannheim/tesseract/wiki) (use the default install path)
  - Linux: `sudo apt install tesseract-ocr`

## Setup (first time only)

Clone or download this repository, then create a virtual environment and install dependencies.

**Windows**
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Calibration

The screen coordinates in `config.toml` are set for a specific resolution. If the scraper clicks in the wrong place, you need to recalibrate.

1. Open Foxhole and navigate to the regiment screen
2. Run the coordinate helper:
   ```
   python locator.py
   ```
3. Hover over the **top-left corner of the name list** — wait 5 seconds
4. Hover over the **bottom-right corner of the name list** — wait 5 seconds
5. Update `config.toml` with the printed coordinates:
   ```toml
   [screen]
   name_crop_x1 = <point 1 x>
   name_crop_y1 = <point 1 y>
   name_crop_x2 = <point 2 x>
   name_crop_y2 = <point 2 y>
   ```
6. Repeat for the activity log panel (`log_crop_*`) and menu offset (`menu_offset_*`)

## Usage

1. Open Foxhole and navigate to the regiment member list
2. Run the scraper:
   ```
   python war_stats.py
   ```
3. Switch to Foxhole within 5 seconds
4. The scraper runs automatically — do not move your mouse

Results are saved to `regiment_activity.csv` in the same folder. The scraper resumes where it left off if interrupted.

## config.toml reference

| Section | Key | Description |
|---------|-----|-------------|
| `[screen]` | `name_crop_*` | Pixel region of the name list column |
| `[screen]` | `log_crop_*` | Pixel region of the activity log panel |
| `[screen]` | `menu_offset_*` | Offset from a player row to the Activity Log menu item |
| `[timing]` | `delay_*` | Seconds to wait between actions (increase if clicks are missing) |
| `[ocr]` | `name_match_cutoff` | Fuzzy match threshold for deduplication (0.0–1.0) |
| `[ocr]` | `scrolls_per_page` | Scroll distance per page — calibrate with `scroll.py` |
