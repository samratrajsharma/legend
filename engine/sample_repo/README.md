# Sample Detector Service

A tiny DETR-style object detection service used to demo KnowIT Phase 0.

- `model.py` — the `Detector` model (initialized in `Detector.__init__`)
- `data.py` — image loading and preprocessing
- `losses.py` — focal loss (handles class imbalance) and cross-entropy
- `infer.py` — inference flow: load -> preprocess -> predict -> postprocess
- `train.py` — the training loop
- `api.py` — the `/detect` endpoint
