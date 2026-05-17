import sys
import os
import pyautogui
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from foxhole.controller import SpaceInterrupt

NOTCHES = 1320

print("\nScroll Test")
time.sleep(3)

intr = SpaceInterrupt().start()
while True:
    print(f"Scrolling {NOTCHES} notch(es)...")
    pyautogui.scroll(-NOTCHES, x=930, y=340)
    if intr.wait(1):
        break

intr.stop()
print("Stopped.")
