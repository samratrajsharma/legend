"""Inference pipeline: image -> preprocess -> model -> postprocess."""
from data import load_image, preprocess
from model import Detector

_MODEL = Detector()


def run_inference(image_path):
    """Full inference flow for a single image.

    Steps: load the image, preprocess it into a tensor, run the model's
    predict() to get raw boxes, then postprocess into final detections.
    """
    image = load_image(image_path)
    tensor = preprocess(image)
    raw = _MODEL.predict(tensor)
    return postprocess(raw)


def postprocess(boxes):
    """Filter detections by confidence score threshold."""
    return [b for b in boxes if b["score"] > 0.5]
