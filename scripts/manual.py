import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from foxhole import cfg, ocr_activity_log

PLAYER_NAME = "Secret_Operations2"

print("Starting in 5 seconds, open the activity log in game...")
time.sleep(5)

data = ocr_activity_log(PLAYER_NAME)
data["player_name"] = PLAYER_NAME

output_csv = cfg.paths.output / cfg.output.csv
df = pd.DataFrame([data])
df.to_csv(output_csv, mode="a", header=False, index=False)
print(f"Appended {PLAYER_NAME} to {output_csv}")
