import json
from pathlib import Path
from PIL import Image   # pip install pillow

# --- 경로 설정 ---------------------------------------------------------
IMG_DIR = Path("dataset/images")
ANNO_DIR = Path("annotations")
LABEL_DIR = Path("dataset/labels")
LABEL_DIR.mkdir(exist_ok=True)

# --- 클래스 이름 → ID 매핑 ---------------------------------------------
# UI에서 사용한 라벨 순서 그대로 맞춤
CLASS_NAME_TO_ID = {
    "hole": 0,
    "scratch": 1,
    "burr": 2,
    "text_error": 3,
    "cnt_error": 4,
    "locate_error": 5,
}

# --- 이미지 파일 찾기 (stem = '027' 등) --------------------------------
def find_image(stem: str) -> Path:
    for ext in [".jpg", ".jpeg", ".png", ".bmp"]:
        p = IMG_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {stem}.* (images 폴더)")

# --- 한 개 JSON → YOLO txt 변환 ---------------------------------------
def convert_one(json_path: Path):
    stem = json_path.stem  # '027'
    img_path = find_image(stem)

    # 이미지 크기
    with Image.open(img_path) as im:
        w, h = im.size  # (width, height)

    # JSON 로드 (리스트 형태)
    with open(json_path, "r", encoding="utf-8") as f:
        annos = json.load(f)

    lines = []

    for obj in annos:
        # polygon 타입만 사용
        if obj.get("atype") != "polygon":
            continue

        label = obj.get("label")
        if label not in CLASS_NAME_TO_ID:
            # 정의되지 않은 클래스는 건너뜀
            continue
        cls_id = CLASS_NAME_TO_ID[label]

        pts = obj.get("points") or []
        if len(pts) < 3:
            # 최소 삼각형 이상일 때만 사용
            continue

        # 정규화 및 평탄화
        norm_coords = []
        for x, y in pts:
            x_n = x / w
            y_n = y / h
            norm_coords.append(f"{x_n:.6f}")
            norm_coords.append(f"{y_n:.6f}")

        # 원하는 포맷:
        # class x1 y1 x2 y2 ...
        line = f"{cls_id} " + " ".join(norm_coords)
        lines.append(line)

    # TXT 저장
    txt_path = LABEL_DIR / f"{stem}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"converted: {json_path.name} -> {txt_path.name} (polygons: {len(lines)})")


# --- 전체 변환 실행 ----------------------------------------------------
def main():
    json_files = sorted(ANNO_DIR.glob("*.json"))
    if not json_files:
        print("annotations 폴더에 json 파일이 없습니다.")
        return

    for jp in json_files:
        convert_one(jp)


if __name__ == "__main__":
    main()
