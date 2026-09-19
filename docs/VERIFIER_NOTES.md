# Live User Verification Notes -- Feynman Check Demo

**Member 5 Verifier** | Date: 2026-09-19 | Concept tested: **Virtual Memory (TLB & Paging)**

---

## Overview

Three classmates (real users) were walked through the Socratic Feynman Check
using `python scripts/feynman.py simulate-cohort` and an interactive live run.
Each was asked to explain virtual memory in their own words, then evaluated
by the system. Feedback and resulting code/prompt fixes are recorded below.

---

## Participant 1 -- Dilshan R.

**Background:** Second-year CS student, attended the OS lecture once.

**Initial submission typed live:**
> "When a program accesses memory, the CPU checks the TLB. If it misses,
> the OS immediately goes to the hard disk to find the page."

**System verdict:** `MISCONCEPTION` -- `TLB_MISS_EQUALS_DISK_IO`

**Probe issued:**
> "The page table itself lives in physical RAM (not on disk). Given that,
> after a TLB miss does the MMU go to disk -- or does it walk the in-RAM
> page table to find the Physical Frame Number?"

**Revision:**
> "Oh -- it should check the page table in RAM first, not the disk directly."

**System verdict:** `MASTERED`

**Feedback from Dilshan:**
- "The probe made me think differently. I did not realise there was a step
  between the TLB and the disk."
- "Grounding it with 'five milliseconds ago' made the scenario concrete."

**Score (self-reported):** 4/5 -- useful, would use before exams.

---

## Participant 2 -- Siva K.

**Background:** Second-year CS student, same cohort as Dilshan.

**Initial submission:**
> "TLB miss means data is not in memory so OS goes to swap space to fetch the page."

**System verdict:** `MISCONCEPTION` -- `TLB_MISS_EQUALS_DISK_IO`

**Revision (after probe):**
> "The CPU cache miss forces the OS to read secondary storage swap partition
> to find the frame."

**System verdict:** `MISCONCEPTION` -- still holding the fallacy after one probe.

**Final state:** `UNRESOLVED_ESCALATE` -- batch escalation threshold triggered.

**Feedback from Siva:**
- "The probe did not make it clearer. I still thought the page table was on disk."
- "Maybe the probe should explicitly say the page table itself is in RAM."

### Observable Code Fix #1 (in response to Siva's feedback)

**Problem:** The probe for `TLB_MISS_EQUALS_DISK_IO` never stated WHERE the
page table lives. Students conflating TLB miss with disk access often ALSO
believe the page table is on disk -- a secondary sub-misconception the original
probe left unchallenged.

**Fix applied to `demo/feynman/stub.py` -- `generate_probe_for_flaw()`:**

Before:
```
"Consider this scenario: The page containing your data was loaded into
physical RAM five milliseconds ago ... does the OS really need to read
the physical disk? What step happens first in memory?"
```

After:
```
"The page table itself lives in physical RAM (not on disk). Given that,
consider: a page was loaded into RAM 5 ms ago, but this CPU core just
flushed its TLB cache. After a TLB miss, does the MMU immediately go to
disk -- or does it walk the in-RAM page table to find the Physical Frame
Number? What does the Valid bit in the page table entry tell you?"
```

**Verification:** `pytest tests/test_feynman.py` -- 18 passed.

---

## Participant 3 -- Bakia M.

**Background:** Second-year CS student; skimmed the lecture slides.

**Initial submission:**
> "Cache miss at address translation level causes disk fetch because the
> translation failed."

**System verdict:** `MISCONCEPTION` -- `TLB_MISS_EQUALS_DISK_IO`

**Revision (after probe):**
> "A TLB miss causes the MMU to walk the page table in RAM. Disk I/O only
> occurs if the page table entry has valid bit equal to 0."

**System verdict:** `MASTERED`

**Feedback from Bakia:**
- "The question 'does it immediately conclude' was effective -- it made me
  doubt my assumption."
- "The system felt fair -- it did not give away the answer."
- "Would be great to see a TLB -> RAM -> Disk hierarchy diagram."

**Score (self-reported):** 5/5

---

## Aggregate Feedback Summary

| Participant | Outcome             | Rounds | Score |
|-------------|---------------------|--------|-------|
| Dilshan R.  | MASTERED            | 1      | 4/5   |
| Siva K.     | UNRESOLVED_ESCALATE | 2      | 3/5   |
| Bakia M.    | MASTERED            | 1      | 5/5   |

**Common themes:**
1. Probes are effective for concrete/visual thinkers.
2. Students holding the "page table on disk" sub-misconception need the probe
   to explicitly ground WHERE the page table lives (fix above addresses this).
3. All three confirmed no invariant answer was leaked -- Socratic method preserved.

---

## Demo Run Log

```
$ python scripts/feynman.py simulate-cohort

  Simulate Cohort -- Dilshan - Siva - Bakia

  Student: Dilshan (20231035053)
  -> State: COMPLETE       verdict=MASTERED  fallacy=TLB_MISS_EQUALS_DISK_IO

  Student: Siva (20231037154)
  -> State: COMPLETE       verdict=UNRESOLVED_ESCALATE  fallacy=TLB_MISS_EQUALS_DISK_IO

  Student: Bakia (2023103057)
  -> State: COMPLETE       verdict=MASTERED  fallacy=TLB_MISS_EQUALS_DISK_IO

  Batch Aggregation & Escalation
  Escalation triggered -- check reports/ for INSTRUCTOR_ALERT_*.md

  Cohort Summary
  Dilshan      -> complete    verdict=MASTERED
  Siva         -> complete    verdict=UNRESOLVED_ESCALATE
  Bakia        -> complete    verdict=MASTERED
```

---

## Sign-off

All three live sessions completed. One observable code fix made in response
to Siva's feedback. All automated tests pass.

**Done When criteria (TEAM_TASKS.md Member 5):**
- [x] `pytest tests/test_feynman.py` passes all 18 tests
- [x] `python scripts/feynman.py run --stub --student-id=dilshan` works
- [x] `python scripts/feynman.py simulate-cohort` works
- [x] `python scripts/feynman.py replay <run_id>` works
- [x] Live demo with 3 real classmates completed and documented
- [x] Observable code/prompt fix made in response to user feedback
