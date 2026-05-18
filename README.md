# Foxhole Regiment Scraper
```
                            ╱|、
                          (˚ˎ 。7
                          |、˜〵        
                          じしˍ,)ノ
```

Automatically scrapes activity log stats for every member of your regiment and saves them to a CSV. The scraper opens the regiment screen, OCRs each player name, clicks through to their activity log, reads the stats, and resumes where it left off if interrupted.

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

## Usage

1. Open Foxhole — the game must be fullscreen
2. Navigate to the regiment member list
3. Run the scraper:
   ```
   python regi_stats.py
   ```
4. Switch to Foxhole within the startup delay (default 5 seconds)
5. Do not move your mouse — the scraper runs automatically

Results are saved to `output/regiment_activity.csv`. The scraper checks the regiment member count before starting; if the CSV already contains a complete record for every member it exits immediately. Partial records (fields that failed OCR) are flagged and rescanned on the next run.

## Calibration

All coordinates in `config.toml` are defined at 1920×1080 and auto-scaled to your actual resolution at startup. If the scraper clicks in the wrong place, recalibrate the reference values.

### Coordinate helper (`scripts/locator.py`)

Prints the screen position of two points you hover over, plus their offset. Use it to calibrate any crop region or menu offset.

```
python scripts/locator.py
```

1. Hover over your first point and wait 5 seconds
2. Hover over your second point and wait 5 seconds
3. Update the relevant fields in `config.toml`

### Scroll calibration (`scripts/scroll.py`)

Repeatedly scrolls the name list by `scrolls_per_page` notches so you can tune the value until exactly one page advances per scroll. Press **Space** to stop.

```
python scripts/scroll.py
```

Update `scrolls_per_page` in `config.toml` once the scroll distance is correct.

## config.toml reference

| Section | Key | Description |
|---------|-----|-------------|
| `[display]` | `reference_width/height` | Resolution the coordinates were calibrated on; all pixel values are auto-scaled at runtime |
| `[screen]` | `name_crop_*` | Pixel region of the name list column |
| `[screen]` | `log_crop_*` | Pixel region of the activity log panel |
| `[screen]` | `member_count_crop_*` | Pixel region of the member count header; tune with `debug/grab_member_count.png` |
| `[screen]` | `menu_offset_*` | Offset from a player row to the context menu (unused — button is found by template match) |
| `[timing]` | `startup_delay` | Seconds before the scraper starts — time to switch to Foxhole |
| `[timing]` | `delay_*` | Seconds to wait between actions; increase if clicks are missing |
| `[ocr]` | `scrolls_per_page` | Scroll notches per page — calibrate with `scripts/scroll.py` |
| `[ocr]` | `scroll_to_top_multiplier` | How many pages-worth to scroll up when resetting to the top |
| `[ocr]` | `min_players_per_page` | Minimum players expected per page; triggers a rescan if fewer are detected |
| `[ocr]` | `max_scan_retries` | Number of rescan attempts before accepting a low player count |
| `[ocr]` | `name_match_cutoff` | Fuzzy match threshold for name deduplication (0.0–1.0) |
| `[ocr]` | `key_match_cutoff` | Fuzzy match threshold for stat key normalisation (0.0–1.0) |
| `[ocr]` | `button_match_threshold` | Template match confidence required to accept the Activity Log button (0.0–1.0) |
| `[ocr]` | `context_menu_search_w/h` | Size of the region searched for the Activity Log button after each click |

## Debug output

Every run saves intermediate images to `debug/` so you can diagnose OCR or click failures:

| File | Contents |
|------|----------|
| `grab_name_scan.png` | Preprocessed name list fed to Tesseract |
| `grab_member_count.png` | Preprocessed member count header |
| `grab_context_menu.png` | Full screenshot taken after clicking a player name |
| `grab_context_menu_search.png` | Cropped region searched for the Activity Log button |
| `grab_activity_log_crop.png` | Raw crop of the activity log panel |
| `grab_activity_log_processed.png` | Preprocessed version fed to Tesseract |
