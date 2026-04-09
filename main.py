import os
import uvicorn
from backend.app.main import app

if __name__ == "__main__":
    # Get port from environment variable, default to 8000
    port = int(os.environ.get("PORT", 8000))
    # Run uvicorn server
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, log_level="info")
