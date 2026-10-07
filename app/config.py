import os
from pathlib import Path

# Must be set before importing any model library.
for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
    os.environ[name] = "1"

DATA = Path(os.environ.get("DATA_ROOT", "/var/lib/docutranslate"))
MODELS = Path(os.environ.get("MODEL_ROOT", "/opt/docutranslate/models/translation"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://docutranslate@localhost/docutranslate")
MAX_UPLOAD = int(os.environ.get("UPLOAD_MAX_SIZE", str(100 * 1024 * 1024)))
RUNTIME_URL = os.environ.get("RUNTIME_URL", "http://127.0.0.1:8091")
SECRET = os.environ.get("SESSION_SECRET", "")
RUNTIME_SECRET = os.environ.get("RUNTIME_SECRET", "")
