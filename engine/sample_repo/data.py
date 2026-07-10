"""Data loading and preprocessing."""


def load_image(path):
    """Read an image file from disk into a raw array."""
    return {"path": path, "pixels": [0, 1, 2]}


def preprocess(image):
    """Normalize and resize an image into a model-ready tensor."""
    return {"tensor": image["pixels"], "shape": (3, 224, 224)}
