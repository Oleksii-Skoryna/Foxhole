import pyautogui
import time

print("Hover over your first point...")
time.sleep(5)
pos1 = pyautogui.position()
print(f"Point 1: {pos1}")

print("Hover over your second point...")
time.sleep(5)
pos2 = pyautogui.position()
print(f"Point 2: {pos2}")

print(f"\nOffset: x={pos2.x - pos1.x}, y={pos2.y - pos1.y}")