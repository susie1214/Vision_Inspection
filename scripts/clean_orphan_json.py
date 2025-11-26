# C:\VISION\scripts\clean_orphan_json.py

from pathlib import Path
import os

# 폴더 경로 설정 (필요하면 수정)
BASE_DIR = Path(r"C:\VISION")          # 프로젝트 루트
IMG_DIR = BASE_DIR / "online_capture" / "images"
JSON_DIR = BASE_DIR / "online_capture" / "json"

def main():
    if not IMG_DIR.is_dir() or not JSON_DIR.is_dir():
        print("[ERROR] 이미지/JSON 폴더 경로를 확인하세요.")
        print(f"IMG_DIR  = {IMG_DIR}")
        print(f"JSON_DIR = {JSON_DIR}")
        return

    # 1. 현재 남아있는 이미지 파일 이름(확장자 제외) 수집
    img_stems = set(p.stem for p in IMG_DIR.glob("*.jpg"))

    # 필요하면 png도 같이 쓰고 싶을 때:
    # img_stems |= set(p.stem for p in IMG_DIR.glob("*.png"))

    print(f"[INFO] 이미지 파일 개수: {len(img_stems)}")

    deleted = 0
    skipped = 0

    # 2. JSON 폴더를 돌면서, 같은 이름의 이미지가 없는 JSON 삭제
    for json_path in JSON_DIR.glob("*.json"):
        stem = json_path.stem

        if stem not in img_stems:
            try:
                os.remove(json_path)
                deleted += 1
                print(f"[DEL] {json_path.name} (이미지 없음)")
            except OSError as e:
                print(f"[WARN] 삭제 실패: {json_path.name} - {e}")
        else:
            skipped += 1

    print("---- 완료 ----")
    print(f"삭제된 JSON : {deleted}개")
    print(f"남겨둔 JSON : {skipped}개")


if __name__ == "__main__":
    main()
