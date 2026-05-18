try:
    import tomllib
except ImportError:
    import tomli as tomllib  # pip install tomli for Python < 3.11

from pathlib import Path

import pyautogui
from pydantic import BaseModel, Field, ValidationError


class PathsConfig(BaseModel):
    output: Path
    logs: Path
    debug: Path


class OutputConfig(BaseModel):
    csv: str


class DisplayConfig(BaseModel):
    reference_width: int = Field(gt=0)
    reference_height: int = Field(gt=0)


class ScreenConfig(BaseModel):
    name_crop_x1: int
    name_crop_y1: int
    name_crop_x2: int
    name_crop_y2: int
    menu_offset_x: int
    menu_offset_y: int
    log_crop_x1: int
    log_crop_y1: int
    log_crop_x2: int
    log_crop_y2: int
    member_count_crop_x1: int
    member_count_crop_y1: int
    member_count_crop_x2: int
    member_count_crop_y2: int


class TimingConfig(BaseModel):
    move_duration: float = Field(gt=0)
    delay_window_focus: float = Field(ge=0)
    delay_click: float = Field(ge=0)
    delay_log_open: float = Field(ge=0)
    delay_retry: float = Field(ge=0)
    delay_scroll: float = Field(ge=0)
    delay_keypress: float = Field(ge=0)
    delay_regiment_open: float = Field(ge=0)
    startup_delay: float = Field(ge=0)


class OcrConfig(BaseModel):
    name_crop_padding: int = Field(ge=0)
    name_conf_threshold: int = Field(ge=0, le=100)
    name_match_cutoff: float = Field(ge=0.0, le=1.0)
    key_match_cutoff: float = Field(ge=0.0, le=1.0)
    scrolls_per_page: int = Field(gt=0)
    scroll_to_top_multiplier: int = Field(gt=0)
    click_y_offset: int
    mouse_park_y_offset: int
    min_players_per_page: int = Field(gt=0)
    max_scan_retries: int = Field(gt=0)
    context_menu_search_w: int = Field(gt=0)
    context_menu_search_h: int = Field(gt=0)
    button_match_threshold: float = Field(ge=0.0, le=1.0)
    expected_keys: list[str]


class AppConfig(BaseModel):
    paths: PathsConfig
    output: OutputConfig
    display: DisplayConfig
    screen: ScreenConfig
    timing: TimingConfig
    ocr: OcrConfig


def _scale_to_screen(config: AppConfig) -> AppConfig:
    sw, sh = pyautogui.size()
    sx = sw / config.display.reference_width
    sy = sh / config.display.reference_height
    if sx == 1.0 and sy == 1.0:
        return config

    screen_data = {}
    for field, value in config.screen.model_dump().items():
        if '_x' in field:
            screen_data[field] = round(value * sx)
        elif '_y' in field:
            screen_data[field] = round(value * sy)
        else:
            screen_data[field] = value

    ocr_data = config.ocr.model_dump()
    ocr_data['name_crop_padding']   = round(ocr_data['name_crop_padding']   * sx)
    ocr_data['click_y_offset']      = round(ocr_data['click_y_offset']      * sy)
    ocr_data['mouse_park_y_offset'] = round(ocr_data['mouse_park_y_offset'] * sy)

    return config.model_copy(update={
        'screen': ScreenConfig(**screen_data),
        'ocr':    OcrConfig(**ocr_data),
    })


def _load(path: Path = Path(__file__).parent.parent / "config.toml") -> AppConfig:
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"config.toml not found at {path}")
    try:
        return _scale_to_screen(AppConfig(**raw))
    except ValidationError as e:
        raise ValueError(f"Invalid config.toml:\n{e}") from e


cfg = _load()
