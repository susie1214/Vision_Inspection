# coco_to_yolo.py
import json, os
from pathlib import Path

COCO_JSON = "dataset/annotations.json"
IMG_DIR = "dataset/images"
OUT_LBL_DIR = "dataset/labels"
os.makedirs(OUT_LBL_DIR, exist_ok=True)

with open(COCO_JSON, "r", encoding="utf-8") as f:
    coco = json.load(f)

# category_id → 0-index 매핑
cat_map = {}
for i, c in enumerate(sorted(coco["categories"], key=lambda x: x["id"])):
    cat_map[c["id"]] = i

# image_id → size, filename
img_map = {im["id"]: (im["file_name"], im["width"], im["height"]) for im in coco["images"]}

# YOLO txt 생성
for ann in coco["annotations"]:
    img_id = ann["image_id"]
    cat_id = cat_map[ann["category_id"]]
    fname, W, H = img_map[img_id]

    x, y, w, h = ann["bbox"]
    cx = (x + w / 2) / W
    cy = (y + h / 2) / H
    ww = w / W
    hh = h / H

    stem = os.path.splitext(fname)[0]
    out_path = Path(OUT_LBL_DIR) / f"{stem}.txt"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"{cat_id} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}\n")

print("COCO → YOLO 변환 완료")
