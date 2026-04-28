import logging
import time

import pyautogui

from .config import cfg

logger = logging.getLogger(__name__)


def smooth_click(x: int, y: int) -> None:
    logger.debug(f"Clicking ({x}, {y})")
    pyautogui.moveTo(x, y, duration=cfg.timing.move_duration)
    pyautogui.click()


def smooth_move(x: int, y: int) -> None:
    logger.debug(f"Moving to ({x}, {y})")
    pyautogui.moveTo(x, y, duration=cfg.timing.move_duration)


def scroll_down_one_page() -> None:
    logger.debug(f"Scrolling {cfg.ocr.scrolls_per_page} notches...")
    cx = (cfg.screen.name_crop_x1 + cfg.screen.name_crop_x2) // 2
    cy = (cfg.screen.name_crop_y1 + cfg.screen.name_crop_y2) // 2
    smooth_move(cx, cy)
    pyautogui.scroll(-cfg.ocr.scrolls_per_page)
    time.sleep(cfg.timing.delay_scroll)


def open_regiment_screen() -> None:
    pyautogui.press("f1")
    time.sleep(cfg.timing.delay_regiment_open)


def close_activity_log() -> None:
    pyautogui.press("escape")
    time.sleep(cfg.timing.delay_keypress)
    open_regiment_screen()
