try:
    import tomllib
except ImportError:
    import tomli as tomllib  # pip install tomli for Python < 3.11

from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class PathsConfig(BaseModel):
    output: Path
    logs: Path
    debug: Path


class OutputConfig(BaseModel):
    csv: str


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


class OcrConfig(BaseModel):
    name_crop_padding: int = Field(ge=0)
    name_match_cutoff: float = Field(ge=0.0, le=1.0)
    key_match_cutoff: float = Field(ge=0.0, le=1.0)
    scrolls_per_page: int = Field(gt=0)
    click_y_offset: int
    mouse_park_y_offset: int
    expected_keys: list[str]


class AppConfig(BaseModel):
    paths: PathsConfig
    output: OutputConfig
    screen: ScreenConfig
    timing: TimingConfig
    ocr: OcrConfig


def _load(path: Path = Path(__file__).parent.parent / "config.toml") -> AppConfig:
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"config.toml not found at {path}")
    try:
        return AppConfig(**raw)
    except ValidationError as e:
        raise ValueError(f"Invalid config.toml:\n{e}") from e


cfg = _load()
