# Good Badminton Web Demo

## What it is

A local-first web wrapper around the original Good-Badminton analysis pipeline.

Workflow:

1. Upload a recorded badminton match video
2. Calibrate the court in the browser
3. Queue a single local analysis job
4. Review the annotated video, heatmap, scatter plot, and downloadable outputs

## Backend

Create a Python virtual environment and install both analysis and web dependencies:

```bash
python3 -m venv .venv-web
source .venv-web/bin/activate
pip install -r requirements.txt -r web-requirements.txt
python -m web.api.run
```

Backend URL:

```text
http://127.0.0.1:8000
```

## Frontend

```bash
cd web/frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

## Notes

- The demo runs best with `yolo11n-pose.pt` available to Ultralytics.
- If `weights/yolo11s-ball.pt` is missing, the system now degrades gracefully and skips shuttlecock detection while still producing pose, court, and movement outputs.
- Outputs are written to `results/web/<job_id>/`.
- Uploaded videos and calibration assets are stored under `storage/`.
