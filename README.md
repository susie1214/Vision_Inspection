# 🛠️ Industrial Vision Inspection – Brake Disc Defect Detection
---
**Automated Labeling Tool + YOLO11-Seg Fine-Tuning for Burr / Scratch / Hole Detection**

**📌 프로젝트 개요**

본 프로젝트는 산업현장(Brake Disc 생산 라인)에서 발생하는 주요 결함인
Burr, Scratch, Hole을 자동 검출하기 위해 제작된 라벨링 툴 + 학습/추론 파이프라인 통합 Vision 시스템입니다.  
현장 작업자가 직접 검수하던 공정을 세그멘테이션 기반 자동화하여
검출 정확도 향상, 작업 시간 절감, 라인 품질 일관성 확보를 목표로 합니다.

---
**🚀 주요 기능 요약**  
✔ 1. 커스텀 라벨링 웹툴

Rectangle / Polygon / Point 3가지 어노테이션 지원
클래스 색상 구분 (burr / scratch / hole)
이미지 삭제 / Annotation 삭제 기능
COCO-style JSON 자동 매칭
YOLO11-Seg 학습에 맞춘 Mask 생성 + 라벨 변환 자동 Export

✔ 2. YOLO11-Seg 기반 결함 검출

- 라벨링 웹툴 (Rectangle / Polygon / Point 지원)  

  - Burr / Scratch / Hole 클래스 색상 구분

  - COCO 형식 JSON 자동 저장 및 Mask 이미지 자동 생성

  - YOLO11-Seg 형식으로 자동 변환 Export  

 -YOLO11-Seg 기반 결함 검출

- 산업용 조명 · 반사 · 노이즈 환경 대응

  - 세그멘테이션으로 미세 결함까지 검출
  
  - 실시간 인퍼런스 구조 (FPS 최적화)

- 자동화 데이터 파이프라인  
  
  - COCO → YOLO11-Seg 라벨 변환 스크립트 포함

   -자동 Train / Validation / Test 분할 (split_100.py)

   -클래스 불균형 대응(오버샘플링 / 가중치 손실) 

- 현장 적용 구조

  - GigE/USB 산업 카메라 입력 지원

   -조명 편차 보정 기능(이미지 Enhance)

   -결함 발견 시 로그 저장 및 PLC 연동 가능 (옵션)

---
**📂 프로젝트 구조**
```
VISION_PROJECT/
│
├── labeling_tool/             # Web annotation tool
│   ├── public/
│   ├── src/
|   |── annotations/            
│   └── storage/                # annotation JSON + mask export
│
├── dataset/
│   ├── images/                   # original images
│   ├── labels/           
│
├── training/
│   ├── train.py               # YOLO11-Seg fine-tuning script
│   └── data.yaml            # class & data config
│
├── coco_to_yolo.py
├── convert_json_to_yolo_seg.py
├── HikrobotGigE.py
│
├── scripts
│   ├── capture_and_label.py
│   ├── clean_orphan_json.py
|   |── split_train_val.py    
│   └── train_tolo11_seg.bat
|
└── README.md
```
---
**🧩 라벨링 툴 기능 상세**  
```
● Annotation 타입 지원  
Type	용도
Rectangle	단순 스크래치 등 직사형 결함
Polygon	Burr, Hole 등 불규칙 패턴
Point	중심점 필요 시
● 클래스 색상  
Burr → Red
Scratch → Blue
Hole → Green
● Export 형식  
annotations.json (COCO format)
mask_xxxx.png (세그멘테이션 mask)
YOLO11-Seg txt 자동 변환
```
<img width="1264" height="728" alt="image" src="https://github.com/user-attachments/assets/f579e5c4-cfdf-4424-a2dc-08c7b0d8c700" />
<img width="496" height="643" alt="image" src="https://github.com/user-attachments/assets/a14b65c4-f597-451b-9c65-e1dd660597cd" />

---
**🧠 YOLO11-Seg 학습 설정**  
```
# config.yaml
path: ./dataset/yolo11_seg
train: train
val: valid
test: test

names:
  0: burr
  1: scratch
  2: hole
```
---
**🎯 추론 파이프라인 (산업현장용)**  

GigE 카메라 프레임 수신
전처리(노이즈 제거, 샤프닝, 밝기 표준화)
YOLO11-Seg 추론
Mask → Defect Region → Class별 색상 표시
결함 로그 저장 / 생산 라인 신호 전송(옵션)

---
**🖥️ 실시간 추론 예시 코드**  
```
from ultralytics import YOLO
import cv2
model = YOLO("best.pt")
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    result = model.predict(frame, conf=0.35)
    annotated = result[0].plot()
    cv2.imshow("Defect Detection", annotated)
    
    if cv2.waitKey(1) == 27:
        break
```
        
---
**⚙️ COCO → YOLO11-Seg 변환 코드 포함**

segmentation polygon → YOLO mask format
bbox → txt 변환
자동 디렉터리 분할(split_100.py 포함)

---
**📈 정확도 개선 전략(현장 기준)**

조명 균일성 확보(하이키 조명 + 확산 돔 라이트)
ROI(디스크 영역) 자동 추출로 오검출 감소
Class imbalance → Oversampling / Weighted Loss
Polygon mask로 Burr/Scratch 경계 정확도 개선

---
**🏭 실제 산업 적용 시나리오**

컨베이어 위 Brake Disc 영상 실시간 수집
제품 통과 시 자동 캡처 및 결함 추론
결함 영역 세그멘테이션 표시
NG 판정 시 PLC로 reject signal 전송
공정 데이터 DB 기록(추후 품질 개선 분석용)

---
**📑 기술 스택**

Front-end: React, HTML5 Canvas
Back-end: Python FastAPI
Vision Model: YOLO11-Seg
Camera: Hikrobot / Basler GigE
Hardware: Windows
Export Format: COCO, YOLO Seg

---
⭐ Contributors

Developer: Jinkeong
Vision AI Engineer
