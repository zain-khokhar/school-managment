"""WSGI entry point for web deployment (PythonAnywhere, Render, Gunicorn, etc.)."""
import os
from pathlib import Path
from desktop_app.api import create_app
from desktop_app.database import Database

BASE_DIR = Path(__file__).resolve().parent
db_path = os.getenv("ERP_DB_PATH", str(BASE_DIR / "school_erp.sqlite3"))

db = Database(db_path)
application = create_app(db, seed=True, enforce_auth=True, allow_remote=True)
app = application

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=5000, debug=False)

