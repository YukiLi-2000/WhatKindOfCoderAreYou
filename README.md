# WhatKindOfCoderAreYou

WhatKindOfCoderAreYou is a bilingual (English/Chinese) developer persona assessment built with Flask. The main scoring logic, PDF generation, and routes live inside the root `app.py`, while HTML templates, styles, and static assets are stored under `templates/` and `static/`. Persona metadata (titles, copy blocks, etc.) resides in `data/persona_content.json`, and PDF fonts are kept in `fonts/` so multilingual output renders correctly. The project targets local and traditional server deployments—no Vercel-specific setup is required.

## Local Development
1. Use Python 3.11+ and create a virtual environment in the repo root:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Tell Flask where to find the application factory and start the dev server:
   ```bash
   export FLASK_APP=app
   flask run  # or: python -m flask run
   ```
   Visit `http://127.0.0.1:5000/` to use the quiz.
4. Run the automated tests, including the PDF smoke test:
   ```bash
   pytest
   ```
