# pregen_failure_automation

Automation for handling Helm PreGen Failure orders.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

Create a `.env` file from `.env.example` and add your Helm credentials:

```env
HELM_EMAIL=your_email@example.com
HELM_PASSWORD=your_password
HEADLESS=false
DEBUG=false
```

## Run Streamlit App

```powershell
.\.venv\Scripts\streamlit.exe run app.py --server.port 8202
```

Then open:

```text
http://localhost:8501
```

Use **Start automation** to run the workflow. The Streamlit app runs the browser automation in headless mode and streams logs into the fixed-height log panel.

## Run CLI

```powershell
python automation.py
```
