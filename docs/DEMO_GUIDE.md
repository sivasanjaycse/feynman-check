# Hackathon Demo Guide: Socratic Feynman Check & Batch Gap Ping

**Team:** AgentX | **Track:** Multi-Agent Learning Solutions  
**Total Demo Time:** 8-10 minutes | **Presenter:** Any team member

---

## Pre-Demo Checklist (15 Minutes Before)

```bash
# Navigate to project root
cd feynman-check

# Install dependencies
pip install -r requirements.txt

# Clean previous run data for a fresh demo
del feynman.db 2>NUL
del run.db 2>NUL
del data\students\*.json 2>NUL
del data\batch_telemetry.json 2>NUL
del reports\*.md 2>NUL

# Smoke-test stub mode (should complete in under 5 seconds, 0 tokens)
python scripts/feynman.py run --stub --canned=mastered

# List available concepts (proves agnosticism)
python scripts/feynman.py list-concepts
```

---

## The 9-Beat Demo Script

### Beat 0: Opening (30 seconds)

**Say:** "This is AgentX. We built a Socratic AI tutor for OS students at CEG Anna University.
The problem: 42 out of 65 students failed a 10-mark TLB question last semester.
The professor had no idea until grading - weeks after the lecture moved on.
Our agent detects misconceptions in real-time, forces students to confront them
with Socratic counter-examples, and alerts the professor before the next lecture."

---

### Beat 1: Show the Ground Truth (30 seconds)

```bash
type data\concepts\virtual_memory.md
```

**Say:** "The agent is NOT hard-coded. It reads a 1-page markdown file the professor writes.
It derives everything: invariants, fallacy tags, pedagogical counters.
Drop ANY .md file in data/concepts/ and the whole pipeline adapts instantly."

**Highlight:** The `TLB_MISS_EQUALS_DISK_IO` section heading - the machine-readable fallacy tag format.

---

### Beat 2: Ideal Student / Mastered (45 seconds)

```bash
python scripts/feynman.py run --stub --concept=virtual_memory --canned=mastered
```

**Say:** "A student who gets it right immediately. The agent evaluates, detects MASTERED
with 99% confidence, exits cleanly. Smart enough to know when NOT to probe."

**Judges see:** `Final State: MASTERED | Total Tokens: 0`

---

### Beat 3: Dilshan Misconception (45 seconds)

```bash
python scripts/feynman.py run --stub --concept=virtual_memory --canned=dilshan
```

**Say:** "Dilshan says: TLB miss = page fault = disk fetch. This is the exact misconception
42 students had. Watch what happens - the agent REFUSES to accept it."

**Judges see:** `Critic Verdict (Initial): MISCONCEPTION (TLB_MISS_EQUALS_DISK_IO)`

---

### Beat 4: THE BACK-EDGE - The Agentic Moment (60 seconds)

*Continue from Beat 3 - the probe appears in the same run*

**Say:** "This is the back-edge. Instead of grading and moving on, the agent LOOPS BACKWARD.
It generates a Socratic counter-example: 'The page was loaded 5ms ago by another thread.
If a TLB miss occurs right now, does the OS really need to read the disk?'
The agent does NOT give the answer. It creates cognitive dissonance and waits for the student to revise.
This is a genuine directed graph with conditional backward edges - not a linear pipeline."

**Judges see:** The `+--- Socratic Counter-Probe ---+` box with the scenario.

**Reference:** Point to the state machine diagram in Agent_Specification.md Section 6.

---

### Beat 5: The Cognitive Shift (30 seconds)

*Same run - Dilshan's revision shown*

**Say:** "Dilshan revises: The page might already be in physical memory.
The MMU walks the page table in RAM first. Disk read only if valid bit is 0.
The agent re-evaluates: MASTERED. Telemetry saved to data/students/20231035053.json."

---

### Beat 6 and 7: Cohort Simulation + Threshold Break (60 seconds)

```bash
python scripts/feynman.py simulate-cohort --concept=virtual_memory
```

**Say:** "Now we fast-forward. Siva and Bakia submit the same misconception.
The batch aggregator scans all student JSON files - pure Python counting, no LLM -
and detects that TLB_MISS_EQUALS_DISK_IO has occurred 3 times.
Threshold breached. An instructor alert is generated."

**Judges see:** 3 students processed, `Batch State: 3 student telemetry file(s) stored under data/students/`

---

### Beat 8: THE HUMAN PAUSE - The Key Agentic Claim (60 seconds)

```bash
type reports\INSTRUCTOR_ALERT.md
```

**Say:** "The agent HALTS. It does not autonomously intervene in the curriculum.
It writes this instructor brief with real student quotes, a fallacy diagnosis,
and a 2-minute remediation slide outline, and WAITS for human review.
This is the Human-in-the-Loop requirement. The agent knows when to stop."

**Judges see:** `[URGENT CONCEPT GAP DETECTED]` with anonymized student quotes and remediation plan.

---

### Beat 9: Professor Decision (30 seconds)

```bash
python scripts/feynman.py run --stub --concept=virtual_memory --canned=dilshan --interactive
```
*(When prompted `[A]cknowledge / [D]ismiss`, press A)*

**Say:** "Acting as the professor, I press A to acknowledge. The agent resumes,
marks the alert as ACKNOWLEDGED, and the intervention is queued for the next lecture.
The professor retains full control of their curriculum agenda."

---

### BONUS Beat: Concept Agnosticism (30 seconds, if time permits)

```bash
python scripts/feynman.py list-concepts
python scripts/feynman.py run --stub --concept=deadlocks
python scripts/feynman.py simulate-cohort --concept=deadlocks
```

**Say:** "The agent is NOT about virtual memory. Drop any concept markdown into data/concepts/
and it works immediately. Here is deadlocks - it correctly catches the
'cycle alone = deadlock' fallacy and generates a multi-instance counter-example.
Zero Python changes needed."

---

## Fallback Strategy (If Live LLM Fails)

```bash
# Everything works in stub mode - 0 tokens, 0 API calls, 100% deterministic
python scripts/feynman.py run --stub --concept=virtual_memory --canned=dilshan
python scripts/feynman.py simulate-cohort --concept=virtual_memory
```

**Say:** "We maintain a fully deterministic offline mode.
The behavior is identical but uses pre-recorded model responses.
This validates the state machine works correctly independent of LLM variance."

---

## Timing Guide

| Beat | Action | Target Time |
|------|--------|-------------|
| 0 | Opening statement | 0:30 |
| 1 | Show ground truth markdown | 1:00 |
| 2 | Ideal student / mastered | 1:45 |
| 3 | Dilshan misconception | 2:30 |
| 4 | THE BACK-EDGE (probe) | 3:30 |
| 5 | Cognitive shift (revision) | 4:00 |
| 6+7 | Cohort simulation | 5:00 |
| 8 | Human pause + report | 6:00 |
| 9 | Professor acknowledges | 6:30 |
| BONUS | Deadlocks concept demo | 7:00 |
| Q&A | Buffer | 10:00 |

---

## Common Judge Questions and Answers

**Q: "Why is this agentic and not just a chatbot?"**

Three reasons. First, it maintains persistent state across student revisions and across the
entire cohort - a chatbot has no memory. Second, it has a conditional back-edge: it dynamically
decides whether to re-route work backward to Socratic probing or forward to batch aggregation
based on the Critic verdict. Third, it features a genuine Human Pause - it halts autonomous
execution and blocks until a human instructor makes a decision. A chatbot cannot do any of these.

**Q: "What if the LLM gives a wrong verdict?"**

The Critic must return a structured Pydantic schema referencing an exact invariant.
Any attempt to bypass the schema defaults to MISCONCEPTION.
We also cap at max_iterations = 2, bounding the loop deterministically.
In offline/stub mode we proved the state machine works without LLM variance.

**Q: "How do you prevent the Socratic probe from giving away the answer?"**

The probe system prompt instructs the model to ask a diagnostic open question
about a counter-example scenario, not to state the correct answer.
If the model leaks the answer anyway, the Critic will score the next revision
as MASTERED - so the safety net is structural, not just prompt-based.

**Q: "This only works for OS. How does it scale to other subjects?"**

It is fully concept-agnostic by design. Drop any .md file into data/concepts/ with
the proper fallacy tag format and the run command works immediately.
We demonstrated this live with deadlocks. The next concept requires zero Python changes
- just a markdown file from the professor.

**Q: "Why flat JSON files instead of a database?"**

Deliberate architectural choice. Flat JSON means 100% inspectability - you can open
any student file in Notepad and audit every single decision the agent made.
It also means deterministic reproducibility. We benchmarked Python scanning 50 JSON
files in under 50 milliseconds. For a hackathon and classroom deployment, this is the right tradeoff.

**Q: "What is the strongest agentic claim?"**

Beat 4 - the back-edge. Most AI pipelines are linear: input, process, output.
Our agent routes work backward. The Critic evaluates a student explanation, detects
a semantic fallacy, and sends control back to Socratic probing rather than grading
and terminating. A genuine directed graph with conditional backward edges - exactly
what distinguishes an agent from a pipeline.

---

## Key Demo Files Reference

| File | Purpose |
|------|---------|
| `data/concepts/virtual_memory.md` | Ground truth for Beat 1 |
| `data/concepts/deadlocks.md` | Concept agnosticism BONUS demo |
| `data/students/*.json` | Student telemetry (generated live during demo) |
| `data/batch_telemetry.json` | Cluster aggregation (generated live) |
| `reports/INSTRUCTOR_ALERT.md` | Professor brief for Beat 8 |
| `docs/Agent_Specification.md` | Full architecture reference for judges |

---

## Adding a New Concept On the Spot

If a judge challenges you to add a new concept live:

```bash
# 1. Create the concept file following the convention:
# data/concepts/cpu_scheduling.md must contain:
#   ## 2. Common Fallacy Patterns
#   ### `FALLACY_TAG_IN_CAPS`
#   - **Description:** ...
#   - **Pedagogical counter:** ...

# 2. Run it immediately - zero Python changes
python scripts/feynman.py run --stub --concept=cpu_scheduling

# 3. Simulate the cohort
python scripts/feynman.py simulate-cohort --concept=cpu_scheduling

# 4. Show it in catalogue
python scripts/feynman.py list-concepts
```

The agent uses dynamic markdown parsing to extract fallacy tags and generate probes.
Zero Python source changes required.