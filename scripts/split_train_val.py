# C:\VISION\scripts\split_train_val.py
from pathlib import Path
import random
import shutil

BASE_DIR = Path(r"C:\VISION")
IMG_TRAIN = BASE_DIR / "dataset_yolo" / "images" / "train"
LBL_TRAIN = BASE_DIR / "dataset_yolo" / "labels" / "train"
IMG_VAL = BASE_DIR / "dataset_yolo" / "images" / "val"
LBL_VAL = BASE_DIR / "dataset_yolo" / "labels" / "val"

IMG_VAL.mkdir(parents=True, exist_ok=True)
LBL_VAL.mkdir(parents=True, exist_ok=True)

val_ratio = 0.2  # 20%를 validation으로

image_files = list(IMG_TRAIN.glob("*.jpg"))
random.shuffle(image_files)

val_count = int(len(image_files) * val_ratio)
val_files = image_files[:val_count]

for img_path in val_files:
    label_path = LBL_TRAIN / (img_path.stem + ".txt")
    if not label_path.exists():
        continue

    shutil.move(str(img_path), IMG_VAL / img_path.name)
    shutil.move(str(label_path), LBL_VAL / label_path.name)
    print(f"VAL로 이동: {img_path.name}")
