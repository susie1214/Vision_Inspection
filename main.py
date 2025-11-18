import os
import uuid
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Any, Literal, Dict

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    Query,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ---------- paths ----------
ROOT = Path(__file__).parent.resolve()
STORAGE = ROOT / "storage"
STORAGE.mkdir(exist_ok=True)

META = ROOT / "metadata"
META.mkdir(exist_ok=True)

ANNS = ROOT / "annotations"
ANNS.mkdir(exist_ok=True)

PUBLIC = ROOT / "public"
PUBLIC.mkdir(exist_ok=True)

# ---------- app ----------
app = FastAPI(title="Labeling API (file-only + export)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 이미지 파일 정적 서빙
app.mount("/storage", StaticFiles(directory=str(STORAGE)), name="storage")
app.mount("/assets", StaticFiles(directory=str(PUBLIC)), name="assets")


# ---------- schemas ----------
class AnnIn(BaseModel):
    id: Optional[str] = None
    image_id: str
    atype: Literal["bbox", "polygon", "mask", "text"] = "bbox"
    label: str = "object"
    bbox: Optional[list[float]] = None
    points: Optional[list[list[float]]] = None
    text: Optional[str] = None
    attrs: Optional[dict[str, Any]] = None


class AnnOut(AnnIn):
    id: str


# COCO payload
class CocoPayload(BaseModel):
    licenses: Optional[list] = None
    info: Optional[dict] = None
    categories: list
    images: list
    annotations: list


# ---------- helpers ----------
def _ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def _poly_area(flat):
    s = 0.0
    n = len(flat) // 2
    for i in range(n):
        x1, y1 = flat[2 * i], flat[2 * i + 1]
        x2, y2 = flat[2 * ((i + 1) % n)], flat[2 * ((i + 1) % n) + 1]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def meta_path(image_id: str) -> Path:
    return META / f"{image_id}.json"


def ann_path(image_id: str) -> Path:
    return ANNS / f"{image_id}.json"


def read_json(p: Path, default):
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(p: Path, obj):
    _ensure_dir(p)
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, p)


# ---------- routing ----------

# 루트: public/index.html 서빙
@app.get("/")
def root():
    idx = PUBLIC / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"status": "ok", "hint": "put public/index.html"}


# 업로드: 단일
@app.post("/api/images")
def upload_image(file: UploadFile = File(...), project: str = Form("default")):
    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    image_id = uuid.uuid4().hex
    name = f"{image_id}{ext}"
    dst = STORAGE / name
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    info = {
        "id": image_id,
        "filename": file.filename,
        "url": f"/storage/{name}",
        "project": project,
    }
    write_json(meta_path(image_id), info)
    write_json(ann_path(image_id), [])
    return info


# 업로드: 배치
@app.post("/api/images/batch")
async def upload_images_batch(
    files: List[UploadFile] = File(None),
    file: UploadFile = File(None),
    project: str = Form("default"),
):
    selected: List[UploadFile] = []
    if files:
        selected.extend(files)
    if file:
        selected.append(file)
    if not selected:
        raise HTTPException(400, "no files (use 'files' or 'file')")

    saved = []
    for uf in selected:
        ext = os.path.splitext(uf.filename)[1].lower() or ".jpg"
        image_id = uuid.uuid4().hex
        name = f"{image_id}{ext}"
        dst = STORAGE / name
        with dst.open("wb") as f:
            shutil.copyfileobj(uf.file, f)

        info = {
            "id": image_id,
            "filename": uf.filename,
            "url": f"/storage/{name}",
            "project": project,
        }
        write_json(meta_path(image_id), info)
        write_json(ann_path(image_id), [])
        saved.append(info)

    return {"count": len(saved), "items": saved}


# 이미지 목록
@app.get("/api/images")
def list_images(project: str = "default"):
    items = []
    for p in META.glob("*.json"):
        info = read_json(p, {})
        if info.get("project") == project:
            items.append(
                {
                    "id": info["id"],
                    "filename": info["filename"],
                    "url": info["url"],
                }
            )
    items.sort(
        key=lambda x: os.path.getmtime(meta_path(x["id"])),
        reverse=True,
    )
    return items

@app.delete("/api/images/{image_id}")
def delete_image(image_id: str):
    """
    한 이미지에 대해:
    - 실제 이미지 파일(storage)
    - 메타데이터(metadata)
    - 어노테이션(annotations)
    모두 삭제
    """
    info = read_json(meta_path(image_id), None)
    if not info:
        raise HTTPException(404, "image not found")

    # 이미지 파일 삭제
    url = info.get("url")
    if url:
        name = url.split("/")[-1]
        img_path = STORAGE / name
        if img_path.exists():
            img_path.unlink()

    # 메타 / 어노테이션 파일 삭제
    mpath = meta_path(image_id)
    apath = ann_path(image_id)
    if mpath.exists():
        mpath.unlink()
    if apath.exists():
        apath.unlink()

    return {"ok": True}

# 어노테이션 조회
@app.get("/api/annotations", response_model=List[AnnOut])
def get_annotations(image_id: str):
    arr = read_json(ann_path(image_id), [])
    out = []
    for a in arr:
        if "id" not in a or not a["id"]:
            a["id"] = uuid.uuid4().hex
        out.append(a)
    return out


# 어노테이션 저장
@app.post("/api/annotations", response_model=List[AnnOut])
def save_annotations(payload: List[AnnIn]):
    if not payload:
        raise HTTPException(400, "empty payload")
    image_id = payload[0].image_id
    out = []
    for a in payload:
        d = a.model_dump()
        d["id"] = d.get("id") or uuid.uuid4().hex
        out.append(d)
    write_json(ann_path(image_id), out)
    return out


# 어노테이션 단건 삭제
@app.delete("/api/annotations/{image_id}/{ann_id}")
def delete_annotation(image_id: str, ann_id: str):
    arr = read_json(ann_path(image_id), [])
    new_arr = [a for a in arr if a.get("id") != ann_id]
    if len(arr) == len(new_arr):
        raise HTTPException(404, "not found")
    write_json(ann_path(image_id), new_arr)
    return {"ok": True}


# -------- Export: 프로젝트 Zip --------
def _collect_project_items(project: str):
    items = []
    for p in META.glob("*.json"):
        meta = read_json(p, None)
        if not meta or meta.get("project") != project:
            continue
        iid = meta["id"]
        url = meta["url"]  # /storage/<name>
        name = url.split("/")[-1]
        img_path = STORAGE / name
        ann = read_json(ann_path(iid), [])
        items.append(
            {
                "image_id": iid,
                "filename": meta.get("filename"),
                "image_file": str(img_path),
                "annotation_file": str(ann_path(iid)),
                "annotation": ann,
            }
        )
    return items


def _build_zip(project: str, items: list):
    ts = time.strftime("%Y%m%d_%H%M%S")
    zname = f"{project}_export_{ts}.zip"
    zpath = Path(tempfile.gettempdir()) / zname

    import zipfile

    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = {"project": project, "count": len(items), "items": []}
        for it in items:
            img_rel = f"images/{Path(it['image_file']).name}"
            ann_rel = f"annotations/{Path(it['annotation_file']).name}"

            if os.path.exists(it["image_file"]):
                zf.write(it["image_file"], img_rel)

            zf.writestr(
                ann_rel,
                json.dumps(it["annotation"], ensure_ascii=False),
            )

            manifest["items"].append(
                {
                    "image_id": it["image_id"],
                    "filename": it["filename"],
                    "image_path": img_rel,
                    "annotation_path": ann_rel,
                }
            )

        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
    return zpath, zname


@app.get("/api/export")
def export_project_zip(project: str = Query("default")):
    items = _collect_project_items(project)
    if not items:
        raise HTTPException(404, "no items for project")
    zpath, zname = _build_zip(project, items)
    return FileResponse(
        zpath,
        filename=zname,
        media_type="application/zip",
    )


# -------- COCO 관련 엔드포인트 --------
@app.post("/save_annotation")
async def save_annotation(request: Request):
    """
    {
      "image_path": "images/001.jpg",
      "annotations": [ {...}, ... ]
    }
    """
    body = await request.json()
    image_path = body["image_path"]
    annos = body["annotations"]

    stem = Path(image_path).stem
    anno_file = ANNS / f"{stem}.json"

    for obj in annos:
        obj["image_id"] = stem

    with open(anno_file, "w", encoding="utf-8") as f:
        json.dump(annos, f, ensure_ascii=False, indent=2)

    return JSONResponse({"ok": True, "annotation_file": str(anno_file)})


@app.post("/save")
def save_coco(payload: CocoPayload):
    """
    COCO 전체 JSON을 저장하고, 내부 포맷으로 ANNS/<image_id>.json 생성
    """
    if not payload.annotations:
        raise HTTPException(400, "empty payload")

    ts = time.strftime("%Y%m%d_%H%M%S")
    coco_path = ROOT / f"annotations_coco_{ts}.json"
    _ensure_dir(coco_path)
    write_json(coco_path, payload.model_dump())

    img_id_to_name: Dict[int, str] = {}
    for im in payload.images:
        img_id_to_name[im["id"]] = im["file_name"]

    per_image: Dict[int, list] = {}
    for ann in payload.annotations:
        img_id = ann["image_id"]
        per_image.setdefault(img_id, [])

        if ann.get("segmentation"):
            seg = (
                ann["segmentation"][0]
                if isinstance(ann["segmentation"], list) and ann["segmentation"]
                else []
            )
            pts = [
                [float(seg[i]), float(seg[i + 1])]
                for i in range(0, len(seg), 2)
            ]
            item = {
                "id": ann.get("id") or uuid.uuid4().hex,
                "image_id": str(img_id),
                "atype": "polygon",
                "label": str(ann.get("category_id")),
                "points": pts,
                "bbox": ann.get("bbox"),
                "attrs": {"iscrowd": ann.get("iscrowd", 0)},
            }
        else:
            item = {
                "id": ann.get("id") or uuid.uuid4().hex,
                "image_id": str(img_id),
                "atype": "bbox",
                "label": str(ann.get("category_id")),
                "bbox": [float(x) for x in ann.get("bbox", [])],
                "points": None,
                "attrs": {"iscrowd": ann.get("iscrowd", 0)},
            }
        per_image[img_id].append(item)

    for img_id, items in per_image.items():
        write_json(ann_path(str(img_id)), items)

    return {
        "ok": True,
        "file": str(coco_path),
        "images": len(payload.images),
        "anns": len(payload.annotations),
    }


@app.get("/api/coco/export")
def export_coco(project: str = Query("default")):
    images = []
    for p in META.glob("*.json"):
        meta = read_json(p, None)
        if not meta or meta.get("project") != project:
            continue
        iid = meta["id"]
        images.append(
            {
                "id": iid,
                "file_name": meta.get("filename", ""),
                "width": 0,
                "height": 0,
                "license": 0,
                "flickr_url": "",
                "coco_url": "",
                "date_captured": 0,
            }
        )

    annotations = []
    label_set = set()
    ann_id = 1
    for p in ANNS.glob("*.json"):
        arr = read_json(p, [])
        for a in arr:
            label_set.add(a.get("label", "object"))
            image_id = a.get("image_id")
            if a.get("atype") == "polygon" and a.get("points"):
                flat = []
                for x, y in a["points"]:
                    flat.extend([float(x), float(y)])
                bbox = a.get("bbox")
                if not bbox and flat:
                    xs = flat[0::2]
                    ys = flat[1::2]
                    x0, y0 = min(xs), min(ys)
                    w, h = max(xs) - x0, max(ys) - y0
                    bbox = [x0, y0, w, h]
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": a.get("label"),
                        "segmentation": [flat],
                        "area": _poly_area(flat),
                        "bbox": bbox or [0, 0, 0, 0],
                        "iscrowd": int(
                            a.get("attrs", {}).get("iscrowd", 0)
                        ),
                    }
                )
            else:
                bbox = a.get("bbox") or [0, 0, 0, 0]
                w = bbox[2] if len(bbox) > 2 else 0
                h = bbox[3] if len(bbox) > 3 else 0
                annotations.append(
                    {
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": a.get("label"),
                        "segmentation": [],
                        "area": float(w) * float(h),
                        "bbox": [float(x) for x in bbox],
                        "iscrowd": int(
                            a.get("attrs", {}).get("iscrowd", 0)
                        ),
                    }
                )
            ann_id += 1

    labels = sorted(label_set)
    categories = [
        {"id": str(i + 1), "name": lbl, "supercategory": ""}
        for i, lbl in enumerate(labels)
    ]

    coco = {
        "licenses": [{"name": "", "id": 0, "url": ""}],
        "info": {
            "contributor": "",
            "date_created": "",
            "description": project,
            "url": "",
            "version": "",
            "year": "",
        },
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }
    return JSONResponse(coco)
