"""Start the operations console."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_app import create_app

app = create_app()


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5080"))
    print(f"Operations console at http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)
