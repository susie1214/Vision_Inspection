@echo off
cd /d C:\VISION

REM 이미 PowerShell에서 venv 활성화되어 있으면 아래 줄은 생략해도 됨
REM call venv\Scripts\activate.bat

yolo segment train ^
  model=C:\VISION\runs\segment\brake_disc_2002\weights\best.pt ^
  data=C:\VISION\scripts\brake_disc.yaml ^
  epochs=80 ^
  imgsz=640 ^
  batch=8 ^
  lr0=0.005 ^
  lrf=0.01 ^
  weight_decay=0.0005 ^
  patience=15 ^
  cos_lr=True ^
  close_mosaic=10 ^
  hsv_h=0.015 ^
  hsv_s=0.4 ^
  hsv_v=0.4 ^
  degrees=5.0 ^
  translate=0.1 ^
  scale=0.5 ^
  shear=2.0 ^
  perspective=0.0 ^
  flipud=0.0 ^
  fliplr=0.5 ^
  mosaic=0.7 ^
  mixup=0.1 ^
  copy_paste=0.5

pause
