# C:\VISION\scripts\capture_and_label_gige.py
"""
Hikrobot GigE + YOLO11 세그멘테이션 실시간 결함(hole, scratch, burr) 검출 + 자동 저장

- Hikrobot GigE 카메라에서 MVS SDK로 프레임 grab
- ROI(벨트/디스크 영역)만 YOLO11-seg 추론
- 결함이 검출된 프레임만 C:\VISION\online_capture\images / json 에 저장

필요:
    pip install ultralytics opencv-python numpy
    Hikrobot MVS SDK 설치 후 Python Sample(MvImport) 경로 설정
"""

import sys
import time
import ctypes
from ctypes import byref, memset, c_ubyte
from pathlib import Path
import json

import cv2
import numpy as np
from ultralytics import YOLO

# ---------------------------------------------------------
# 0. 공통 경로 / ROI / 클래스 이름 설정
# ---------------------------------------------------------

# YOLO11 세그멘테이션 모델 경로
MODEL_PATH = r"C:\VISION\runs\segment\brake_disc_2002\weights\best.pt" # r"C:\VISION\runs_yolo11\burr_seg_v1\weights\best.pt"

# 저장 베이스 디렉터리
BASE_DIR = Path(r"C:\VISION")
IMG_DIR = BASE_DIR / "online_capture" / "images"
JSON_DIR = BASE_DIR / "online_capture" / "json"
IMG_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)

# ROI (카메라 해상도 기준 좌표) - 실제 화면 보면서 조정
# 예) 컨베이어 녹색 벨트 가운데 디스크만 나오도록 crop
ROI_X0, ROI_Y0 = 100, 100    # 좌상단
ROI_X1, ROI_Y1 = 1600, 1900  # 우하단

# 모델 클래스 인덱스 → 이름
CLASS_NAMES = {
    0: "hole",
    1: "scratch",
    2: "burr",
    # 필요하면 여기에 text_error, cnt_error 등 추가
}

# ---------------------------------------------------------
# 1. MVS SDK 파이썬 모듈 경로 설정
# ---------------------------------------------------------

# 본인 PC에 설치된 MVS Python 예제 경로로 수정
MVS_PY_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
sys.path.append(MVS_PY_PATH)

from MvCameraControl_class import *
from CameraParams_const import *


# ---------------------------------------------------------
# 2. 카메라 초기화 / 종료
# ---------------------------------------------------------

def open_hik_gige_camera(cam_index: int = 0):
    """
    Hikrobot GigE 카메라 오픈 및 스트리밍 시작
    return: (cam 객체, data_buf, payload_size)
    """
    device_list = MV_CC_DEVICE_INFO_LIST()
    tlayer_type = MV_GIGE_DEVICE  # GigE만 사용

    # 1) 장치 열거
    ret = MvCamera.MV_CC_EnumDevices(tlayer_type, device_list)
    if ret != 0:
        print(f"[ERROR] Enum devices failed! ret[0x{ret:x}]")
        sys.exit(1)

    if device_list.nDeviceNum == 0:
        print("[ERROR] No camera found!")
        sys.exit(1)

    if cam_index >= device_list.nDeviceNum:
        print("[ERROR] cam_index out of range")
        sys.exit(1)

    print(f"[INFO] Found {device_list.nDeviceNum} device(s). Use index {cam_index}")

    # 2) 카메라 핸들 생성
    cam = MvCamera()
    stDeviceList = ctypes.cast(
        device_list.pDeviceInfo[cam_index],
        ctypes.POINTER(MV_CC_DEVICE_INFO)
    ).contents

    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print(f"[ERROR] Create handle failed! ret[0x{ret:x}]")
        sys.exit(1)

    # 3) 디바이스 오픈
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"[ERROR] Open device failed! ret[0x{ret:x}]")
        cam.MV_CC_DestroyHandle()
        sys.exit(1)

    # 4) GigE 패킷 사이즈 최적화
    if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
        nPacketSize = cam.MV_CC_GetOptimalPacketSize()
        if int(nPacketSize) > 0:
            ret = cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
            if ret != 0:
                print(f"[WARN] Set Packet Size failed! ret[0x{ret:x}]")
        else:
            print(f"[WARN] Get Packet Size failed! nPacketSize[{nPacketSize}]")

    # 5) 트리거 모드 OFF (프리런)
    ret = cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
    if ret != 0:
        print(f"[ERROR] Set TriggerMode failed! ret[0x{ret:x}]")
        sys.exit(1)

    # 6) 페이로드 크기 가져오기
    stParam = MVCC_INTVALUE()
    memset(byref(stParam), 0, ctypes.sizeof(MVCC_INTVALUE))
    ret = cam.MV_CC_GetIntValue("PayloadSize", stParam)
    if ret != 0:
        print(f"[ERROR] Get PayloadSize failed! ret[0x{ret:x}]")
        sys.exit(1)
    payload_size = stParam.nCurValue

    # 7) 스트리밍 시작
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print(f"[ERROR] StartGrabbing failed! ret[0x{ret:x}]")
        sys.exit(1)

    # 8) 수신 버퍼 할당
    data_buf = (c_ubyte * payload_size)()

    print("[INFO] Camera opened and grabbing started.")
    return cam, data_buf, payload_size


def close_hik_camera(cam):
    """카메라 스트리밍 종료 및 핸들 파괴"""
    if cam is None:
        return
    ret = cam.MV_CC_StopGrabbing()
    if ret != 0:
        print(f"[WARN] StopGrabbing failed! ret[0x{ret:x}]")

    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print(f"[WARN] CloseDevice failed! ret[0x{ret:x}]")

    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print(f"[WARN] DestroyHandle failed! ret[0x{ret:x}]")

    print("[INFO] Camera closed.")


# ---------------------------------------------------------
# 3. 한 프레임을 OpenCV BGR 이미지로 변환
# ---------------------------------------------------------

def grab_frame_bgr(cam, data_buf, payload_size, timeout_ms: int = 1000):
    frame_info = MV_FRAME_OUT_INFO_EX()
    memset(byref(frame_info), 0, ctypes.sizeof(MV_FRAME_OUT_INFO_EX))

    ret = cam.MV_CC_GetOneFrameTimeout(
        data_buf,
        payload_size,
        frame_info,
        timeout_ms
    )
    if ret != 0:
        # 타임아웃 등
        return None

    width = frame_info.nWidth
    height = frame_info.nHeight
    pixel_type = frame_info.enPixelType

    # 1) Mono8
    if pixel_type == PixelType_Gvsp_Mono8:
        img_gray = np.frombuffer(data_buf, dtype=np.uint8,
                                 count=width * height)
        img_gray = img_gray.reshape(height, width)
        img_bgr = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    # 2) RGB8 Packed
    elif pixel_type == PixelType_Gvsp_RGB8_Packed:
        img_rgb = np.frombuffer(data_buf, dtype=np.uint8,
                                count=width * height * 3)
        img_rgb = img_rgb.reshape(height, width, 3)
        # img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        img_bgr = img_rgb

    # 3) BayerRG8 
    elif pixel_type == PixelType_Gvsp_BayerRG8:
        img_bayer = np.frombuffer(data_buf, dtype=np.uint8,
                                  count=width * height)
        img_bayer = img_bayer.reshape(height, width)
        # img_bgr = cv2.cvtColor(img_bayer, cv2.COLOR_BAYER_RG2BGR)
        img_bgr = cv2.cvtColor(img_bayer, cv2.COLOR_BAYER_RG2RGB)
    else:
        print(f"[WARN] Unsupported pixel type: {pixel_type}")
        return None

    return img_bgr


# ---------------------------------------------------------
# 4. YOLO11 세그멘테이션 + 자동 저장 루프
# ---------------------------------------------------------

def run_gige_capture_and_label(
    model_path: str,
    cam_index: int = 0,
    conf_thres: float = 0.5,
    show_window: bool = True
):
    print("[INFO] Loading YOLO11 model...")
    model = YOLO(model_path)

    cam, data_buf, payload_size = open_hik_gige_camera(cam_index)

    idx = 0

    try:
        while True:
            frame = grab_frame_bgr(cam, data_buf, payload_size)
            if frame is None:
                continue

            h, w, _ = frame.shape

            # ROI 범위가 이미지 밖으로 나가지 않도록 clip
            x0 = max(0, min(ROI_X0, w - 1))
            x1 = max(0, min(ROI_X1, w))
            y0 = max(0, min(ROI_Y0, h - 1))
            y1 = max(0, min(ROI_Y1, h))

            roi = frame[y0:y1, x0:x1]
            if roi.size == 0:
                continue

            # YOLO 세그멘테이션 추론
            results = model(
                roi,
                imgsz=640,
                conf=conf_thres,
                verbose=False
            )
            r = results[0]

            has_defect = r.boxes is not None and len(r.boxes) > 0

            # 화면에 박스 시각화 (디버그용)
            if has_defect:
                boxes = r.boxes.xyxy.cpu().numpy()
                cls_ids = r.boxes.cls.cpu().numpy()
                scores = r.boxes.conf.cpu().numpy()
                masks = r.masks.xy if r.masks is not None else [None] * len(boxes)

                for box, cls_id, score in zip(boxes, cls_ids, scores):
                    x1b, y1b, x2b, y2b = box.astype(int)
                    cid = int(cls_id)
                    label = CLASS_NAMES.get(cid, str(cid))
                    txt = f"{label} {score:.2f}"

                    if label == "hole":
                        color = (255, 0, 0)
                    elif label == "scratch":
                        color = (0, 255, 255)
                    elif label == "burr":
                        color = (0, 255, 0)
                    else:
                        color = (255, 255, 255)

                    cv2.rectangle(roi, (x1b, y1b), (x2b, y2b), color, 2)
                    cv2.putText(
                        roi,
                        txt,
                        (x1b, max(y1b - 5, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

            # 결함이 있는 프레임만 저장 (image + json)
            if has_defect:
                stem = f"disc_{idx:06d}"
                img_path = IMG_DIR / f"{stem}.jpg"
                json_path = JSON_DIR / f"{stem}.json"

                cv2.imwrite(str(img_path), roi)

                ann = {
                    "image": str(img_path),
                    "width": roi.shape[1],
                    "height": roi.shape[0],
                    "timestamp": time.time(),
                    "objects": []
                }

                boxes = r.boxes.xyxy.cpu().numpy()
                cls_ids = r.boxes.cls.cpu().numpy()
                scores = r.boxes.conf.cpu().numpy()
                masks = r.masks.xy if r.masks is not None else [None] * len(boxes)

                for box, cls_id, score, poly in zip(boxes, cls_ids, scores, masks):
                    x1b, y1b, x2b, y2b = box.astype(float)
                    cid = int(cls_id)
                    label = CLASS_NAMES.get(cid, str(cid))
                    conf = float(score)

                    obj = {
                        "class_id": cid,
                        "class_name": label,
                        "confidence": conf,
                        "bbox_xyxy": [x1b, y1b, x2b, y2b],
                        "segmentation": poly.tolist() if poly is not None else None
                    }
                    ann["objects"].append(obj)

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(ann, f, ensure_ascii=False, indent=2)

                print(f"[SAVE] {img_path.name} (objects: {len(ann['objects'])})")
                idx += 1

            # ROI 화면 출력
            if show_window:
                cv2.imshow("Hikrobot + YOLO11 (ROI, capture&label)", roi)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

    finally:
        close_hik_camera(cam)
        if show_window:
            cv2.destroyAllWindows()


# ---------------------------------------------------------
# 5. 엔트리 포인트
# ---------------------------------------------------------

if __name__ == "__main__":
    run_gige_capture_and_label(
        model_path=MODEL_PATH,
        cam_index=0,
        conf_thres=0.5,   # false-positive 많으면 0.6~0.7로 올려보기
        show_window=True
    )
