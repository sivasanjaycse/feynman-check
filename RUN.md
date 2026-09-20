# RUN.md

### 1. Prerequisites & Environment Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Ensure the following variables are configured in `.env`:
- `OPENROUTER_API_KEY` — Your OpenRouter API key.
- `BREVO_SMTP_KEY` — Brevo SMTP Master Key for live pedagogical cohort alert dispatch.
- `BREVO_SMTP_FROM` — Verified Brevo sender email (e.g., `sivasanjaidisco@gmail.com`).
- `FACULTY_EMAIL` — Target faculty recipient email for cohort escalation alerts (e.g., `sivasanjayofficial@gmail.com`).

Install dependencies:
```bash
pip install -r requirements.txt
```

---

### 2. Run the Demo (Web Application)

Start the live Feynman Check server:
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at:
- **Student Feynman Interface**: [http://localhost:8000](http://localhost:8000)
  (Students explain lecture concepts in plain English; the Socratic agent probes for latent misconceptions and verifies understanding).
- **Instructor Dashboard**: [http://localhost:8000/instructor](http://localhost:8000/instructor)
  (Real-time cohort clustering, misconception gap telemetry, alert brief previews, and live Brevo SMTP verification).

---

### 3. Terminal Live Stage Simulation

To demonstrate the full autonomous cohort escalation pipeline in under 30 seconds directly in the terminal:
```bash
python simulate_demo.py
```
*Watches simulated students hit the same conceptual roadblock, automatically breaches the 3-student cluster threshold, generates an intervention brief in `reports/INSTRUCTOR_ALERT.md`, and dispatches a real alert email via Brevo SMTP relay to the faculty inbox.*
