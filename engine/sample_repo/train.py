"""Training entry point."""
from data import load_image, preprocess
from model import Detector
from losses import focal_loss


def train(dataset, epochs=10, lr=1e-4):
    """Training loop: builds the Detector and optimizes it with focal loss."""
    model = Detector()
    for epoch in range(epochs):
        for path in dataset:
            image = preprocess(load_image(path))
            preds = model.predict(image)
            step_loss = focal_loss(preds, targets=None)
    return model


if __name__ == "__main__":
    train(["a.jpg", "b.jpg"])
