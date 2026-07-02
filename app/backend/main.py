"""uvicorn launcher for the Know Your Code testbed backend."""
import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    uvicorn.run("app:app", host="127.0.0.1", port=8100, reload=True)
