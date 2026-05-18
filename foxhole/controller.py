import logging
import threading
import time

import pyautogui
import pygetwindow as gw
from pynput import keyboard

from .config import cfg

logger = logging.getLogger(__name__)

_GAME_TITLE = "War"


class SpaceInterrupt:
    def __init__(self):
        self._event = threading.Event()
        self._listener = keyboard.Listener(on_press=self._on_press)

    def _on_press(self, key):
        if key == keyboard.Key.space:
            self._event.set()

    def start(self):
        self._listener.start()
        print("Press SPACE to stop.")
        return self

    def wait(self, timeout=None):
        """Block until space is pressed or timeout expires. Returns True if triggered."""
        return self._event.wait(timeout)

    def stop(self):
        self._listener.stop()


def focus_game_window() -> None:
    """Bring the game window to the foreground via minimize/restore."""
    windows = [w for w in gw.getAllWindows() if w.title.strip() == _GAME_TITLE]
    if not windows:
        raise RuntimeError(
            f"Foxhole window not found (title: '{_GAME_TITLE}'). "
            "Make sure the game is running."
        )
    win = windows[0]
    win.minimize()
    win.restore()
    time.sleep(cfg.timing.delay_window_focus)


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


def scroll_to_top() -> None:
    logger.debug("Scrolling to top of regiment list...")
    cx = (cfg.screen.name_crop_x1 + cfg.screen.name_crop_x2) // 2
    cy = (cfg.screen.name_crop_y1 + cfg.screen.name_crop_y2) // 2
    smooth_move(cx, cy)
    pyautogui.scroll(cfg.ocr.scrolls_per_page * cfg.ocr.scroll_to_top_multiplier)
    time.sleep(cfg.timing.delay_scroll)


def open_regiment_screen() -> None:
    pyautogui.press("f1")
    time.sleep(cfg.timing.delay_regiment_open)


def close_activity_log() -> None:
    pyautogui.press("escape")
    time.sleep(cfg.timing.delay_keypress)
    open_regiment_screen()
