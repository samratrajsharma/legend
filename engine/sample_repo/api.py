"""HTTP API exposing the detector for inference."""
from infer import run_inference


def create_app():
    """Create the web app and register routes (the service entry point)."""
    routes = {}

    def detect(image_path):
        # POST /detect endpoint: the API entry point that triggers inference.
        return run_inference(image_path)

    routes["/detect"] = detect
    return routes


if __name__ == "__main__":
    app = create_app()
