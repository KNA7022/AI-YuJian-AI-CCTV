from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "web"
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
JOBS_DIR = STORAGE_DIR / "jobs"
RESULTS_DIR = ROOT_DIR / "results" / "web"
DATABASE_PATH = STORAGE_DIR / "jobs.db"
FRONTEND_DIST_DIR = WEB_DIR / "frontend" / "dist"

for path in [STORAGE_DIR, UPLOADS_DIR, JOBS_DIR, RESULTS_DIR]:
    path.mkdir(parents=True, exist_ok=True)
