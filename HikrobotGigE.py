"""
Hikrobot GigE + YOLO11 실시간 결함(hole, scratch, burr) 검출 예제
- Windows + MVS SDK + Python
- YOLO11 세그멘테이션 모델 사용 (box만 시각화)

필요:
    pip install ultralytics opencv-python numpy
    MVS SDK 설치 후 MvImport 경로 추가
"""

import sys
import time
import ctypes
from ctypes import byref, memset, c_ubyte
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# ---------------------------
# 1. MVS SDK 파이썬 모듈 경로 설정
# ---------------------------
# 본인 PC에 설치된 경로로 수정할 것
MVS_PY_PATH = r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport"
sys.path.append(MVS_PY_PATH)

from MvCameraControl_class import *
from CameraParams_const import *


# ---------------------------
# 2. 카메라 초기화 / 종료 함수
# ---------------------------

def open_hik_gige_camera(cam_index: int = 0):
    """
    Hikrobot GigE 카메라 오픈 및 스트리밍 시작
    return: (cam 객체, data_buf, payload_size)
    """
    device_list = MV_CC_DEVICE_INFO_LIST()
    tlayer_type = MV_GIGE_DEVICE  # GigE만 사용 (USB도 쓰려면 | MV_USB_DEVICE)

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


# ---------------------------
# 3. 한 프레임 받아서 OpenCV BGR 이미지로 변환
# ---------------------------

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

    # --- 1) Mono8 → Gray → BGR ---------------------------------
    if pixel_type == PixelType_Gvsp_Mono8:
        img_gray = np.frombuffer(data_buf, dtype=np.uint8,
                                 count=width * height)
        img_gray = img_gray.reshape(height, width)
        img_bgr = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    # --- 2) RGB8 Packed → BGR -----------------------------------
    elif pixel_type == PixelType_Gvsp_RGB8_Packed:
        img_rgb = np.frombuffer(data_buf, dtype=np.uint8,
                                count=width * height * 3)
        img_rgb = img_rgb.reshape(height, width, 3)
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    # --- 3) BayerRG8 → BGR (디모자이킹) --------------------------
    elif pixel_type == PixelType_Gvsp_BayerRG8:
        # 1채널 Bayer 패턴 이미지
        img_bayer = np.frombuffer(data_buf, dtype=np.uint8,
                                  count=width * height)
        img_bayer = img_bayer.reshape(height, width)

        # Bayer RG 패턴 → BGR 로 변환
        img_bgr = cv2.cvtColor(img_bayer, cv2.COLOR_BAYER_RG2RGB)

    else:
        print(f"[WARN] Unsupported pixel type: {pixel_type}")
        return None

    return img_bgr



# ---------------------------
# 4. YOLO11 실시간 검출 루프
# ---------------------------

# ---------------------------
# 0. 파일 상단 근처에 ROI 좌표 추가
# ---------------------------
ROI_X0, ROI_Y0 = 100, 100    # TODO: 본인 카메라에 맞게 조정
ROI_X1, ROI_Y1 = 1600, 1900  # TODO: 본인 카메라에 맞게 조정

def run_realtime_detection(
    model_path: str,
    cam_index: int = 0,
    conf_thres: float = 0.5,
    show_window: bool = True
):
    print("[INFO] Loading YOLO11 model...")
    model = YOLO(model_path)

    class_names = {
        0: "hole",
        1: "scratch",
        2: "burr",
    }

    cam, data_buf, payload_size = open_hik_gige_camera(cam_index)

    try:
        while True:
            frame = grab_frame_bgr(cam, data_buf, payload_size)
            if frame is None:
                continue

            # 1) ROI 잘라내기 (브레이크 디스크만)
            roi = frame[ROI_Y0:ROI_Y1, ROI_X0:ROI_X1]

            # 2) YOLO 추론은 ROI만 사용
            results = model.predict(
                source=roi,
                imgsz=640,
                conf=conf_thres,
                verbose=False
            )
            r = results[0]

            # 3) ROI 위에 박스 그리기
            if r.boxes is not None:
                boxes = r.boxes.xyxy.cpu().numpy()
                cls_ids = r.boxes.cls.cpu().numpy()
                scores = r.boxes.conf.cpu().numpy()

                for box, cls_id, score in zip(boxes, cls_ids, scores):
                    x1, y1, x2, y2 = box.astype(int)
                    cls_id = int(cls_id)
                    label = class_names.get(cls_id, str(cls_id))
                    txt = f"{label} {score:.2f}"

                    if label == "hole":
                        color = (255, 0, 0)
                    elif label == "scratch":
                        color = (0, 255, 255)
                    elif label == "burr":
                        color = (0, 255, 0)
                    else:
                        color = (255, 255, 255)

                    cv2.rectangle(roi, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        roi,
                        txt,
                        (x1, max(y1 - 5, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

            # 4) ROI만 화면에 출력 → 녹색 배경은 안 보임
            if show_window:
                cv2.imshow("Hikrobot + YOLO11 realtime (ROI)", roi)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

    finally:
        close_hik_camera(cam)
        if show_window:
            cv2.destroyAllWindows()



# ---------------------------
# 5. 엔트리 포인트
# ---------------------------

if __name__ == "__main__":
    # 학습된 YOLO11 세그멘테이션 모델 경로로 수정
    MODEL_PATH = r"runs_yolo11/burr_seg_v1/weights/best.pt"

    run_realtime_detection(
        model_path=MODEL_PATH,
        cam_index=0,       # 여러 대면 인덱스 변경
        conf_thres=0.5,    # 컨베이어에서 false-positive 많으면 0.6~0.7로 올려보기
        show_window=True
    )
