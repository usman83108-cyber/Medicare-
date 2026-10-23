# MediCare+ Website (Flask + SQLite)

A responsive website prototype based on the MediCare+ presentation.

## Included in this version
- Responsive landing page and dashboard
- Add/remove medicine records
- Mark a dose as taken and keep a log
- Decrease estimated stock when a dose is logged
- Low-stock indicators (7 pills or fewer)
- Upload/download/delete prescription files with optional notes
- SQLite database and Render deployment configuration

## Important limitations
- This is a prototype, not a medical device or a substitute for professional advice.
- No real timed push/voice reminders, SMS/email caregiver alerts, pharmacy checkout, payment, OCR, AI interaction checker, or ABHA connection are implemented in this first version.
- Prescription files are stored on the server. Do not upload real patient records until you have implemented authentication, authorization, encryption, retention rules, backups, and a privacy/security review.
- `SECRET_KEY` must be set to a strong secret in production.
- Render's persistent disk is configured in `render.yaml`; persistent disks may require a paid Render plan. Without persistent storage, uploaded files and SQLite data can be lost during redeploy/restart.
- The adherence percentage is only a rough count of logged doses divided by the number of medicines; it is not a clinically meaningful adherence measure.

## Run locally
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Deploy to Render from GitHub
1. Create a GitHub repository named `medicare-plus-website`.
2. Upload the files and folders in this project. Keep `app.py`, `requirements.txt`, and `render.yaml` at the repository root.
3. In Render, choose **New + → Blueprint** and connect the GitHub repository. Render reads `render.yaml`.
4. Review the service settings and deploy.
5. If creating the web service manually instead, use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Add environment variable `SECRET_KEY` with a long random value.
   - Add persistent disk mounted at `/var/data`, set `DATA_DIR=/var/data`, and make sure the selected plan supports disks.
6. Wait for the deploy to finish and open the `onrender.com` URL.

## Basic checks
- Open `/health`; it should return `{"status":"ok","service":"MediCare+"}`.
- Add a test medicine, mark it taken, and check the log and stock.
- Upload a non-sensitive test PDF/image, download it, and delete it.
- Test mobile layout and review Render logs if deployment fails.

## Before real users
Add user accounts and per-user access control before any sensitive data; protect uploads and downloads; configure backups and retention/deletion policies; use HTTPS; review applicable Indian privacy/health-data obligations; test accessibility; and obtain authorized integrations before claiming pharmacy ordering, payment, OCR or clinical interaction checks work.
