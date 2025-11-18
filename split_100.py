# split_100.py
import shutil, os
from pathlib import Path

SRC_IMG = Path("dataset/images")
SRC_LBL = Path("dataset/labels")
DST_IMG = Path("dataset/images")
DST_LBL = Path("dataset/labels")

for p in [DST_IMG/"train", DST_IMG/"test", DST_LBL/"train", DST_LBL/"test"]:
    p.mkdir(parents=True, exist_ok=True)

def move_range(start, end, cls_name):
    # 마지막 2장을 test로, 나머지는 train으로
    test_idx = [end-1, end]
    for i in range(start, end+1):
        stem = f"{i:03d}"
        img = SRC_IMG/f"{stem}.jpg"
        lbl = SRC_LBL/f"{stem}.txt"
        if i in test_idx:
            shutil.copy2(img, DST_IMG/"test"/img.name)
            shutil.copy2(lbl, DST_LBL/"test"/lbl.name)
        else:
            shutil.copy2(img, DST_IMG/"train"/img.name)
            shutil.copy2(lbl, DST_LBL/"train"/lbl.name)

# 001–025 hole, 026–050 burr, 051–075 normal, 076–100 scratch
move_range(1,25,"hole")
move_range(26,50,"burr")
move_range(51,75,"normal")
move_range(76,100,"scratch")
print("train/test 분할 완료")
