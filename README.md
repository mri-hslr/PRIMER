# Primer BKT Prototype v2

The web prototype fixes the previous state-reset issue.

CSV = historical learner evidence.
In-memory session state = current learner state during the demo.

Every new answer updates the current BKT state, so repeated answers actually
continue from the previous state.

Optional OpenAI integration is included. Copy `.env.example` to `.env` and add
your API key. Without a key, the app uses an offline fallback.

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python prototype/app.py
```

Open `http://127.0.0.1:5000`.

The notebook from the original prototype remains the learning-first BKT implementation.
