import pyautogui
import time

print("\nScroll Test")
time.sleep(3)  # time to observe

for notches in [1320]:
    print(f"Scrolling {notches} notch(es)... watch how many rows move.")
    pyautogui.scroll(-notches,x = 930  ,y = 340  )
    time.sleep(1)  # time to observe