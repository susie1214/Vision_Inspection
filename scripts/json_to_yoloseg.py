# C:\VISION\scripts\json_to_yoloseg.py
import json
import shutil
from pathlib import Path

BASE_DIR = Path(r"C:\VISION")
JSON_DIR = BASE_DIR / "online_capture" / "json"
IMG_SRC_DIR = BASE_DIR / "online_capture" / "images"

IMG_DST_DIR = BASE_DIR / "dataset_yolo" / "images" / "train"
LBL_DST_DIR = BASE_DIR / "dataset_yolo" / "labels" / "train"
IMG_DST_DIR.mkdir(parents=True, exist_ok=True)
LBL_DST_DIR.mkdir(parents=True, exist_ok=True)

for json_file in JSON_DIR.glob("*.json"):
    with open(json_file, "r", encoding="utf-8") as f:
        ann = json.load(f)

    w = ann["width"]
    h = ann["height"]

    img_path = Path(ann["image"])
    # 혹시 JSON 안 경로가 절대경로가 아니면, online_capture/images 기준으로 처리
    if not img_path.is_file():
        img_path = IMG_SRC_DIR / img_path.name

    # 이미지 train 폴더로 복사
    dst_img_path = IMG_DST_DIR / img_path.name
    if not dst_img_path.exists():
        shutil.copy2(img_path, dst_img_path)

    lines = []
    for obj in ann["objects"]:
        cid = int(obj["class_id"])
        poly = obj["segmentation"]
        if not poly:
            continue

        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]

        x_c = (min(xs) + max(xs)) / 2 / w
        y_c = (min(ys) + max(ys)) / 2 / h
        bw = (max(xs) - min(xs)) / w
        bh = (max(ys) - min(ys)) / h

        poly_norm = []
        for x, y in poly:
            poly_norm.append(x / w)
            poly_norm.append(y / h)

        line = " ".join(
            [str(cid), f"{x_c:.6f}", f"{y_c:.6f}", f"{bw:.6f}", f"{bh:.6f}"] +
            [f"{v:.6f}" for v in poly_norm]
        )
        lines.append(line)

    if lines:
        txt_path = LBL_DST_DIR / (img_path.stem + ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    print(f"변환 완료: {json_file.name} -> {img_path.stem}.txt")
