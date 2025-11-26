# scripts/train_yolo11_seg.sh
yolo segment train \
  model=runs/segment/brake_disc_2002/weights/best.pt \
  data=brake_disc.yaml \
  epochs=80 \
  imgsz=640 \
  batch=8 \
  lr0=0.005 lrf=0.01 \
  weight_decay=0.0005 \
  patience=15 \
  cos_lr=True \
  close_mosaic=10 \
  hyp=brake_disc_hyp.yaml
