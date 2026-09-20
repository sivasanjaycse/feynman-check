"""
seed_cohort.py — Fabricates initial student telemetry across 4 OOP lectures.

Pre-seeds Student 1 (Alice: 2023101001) and Student 2 (Bob: 2023101002)
with the core misconceptions for:
  - Lecture 1 (oop_lecture_1): CLASS_IS_AN_OBJECT
  - Lecture 2 (oop_lecture_2): PRIVATE_MEMBERS_INHERITED
  - Lecture 3 (oop_lecture_3): INHERITANCE_IS_CODE_REUSE_ONLY
  - Lecture 4 (oop_lecture_4): OVERLOADING_EQUALS_OVERRIDING

Threshold = 3.
With 2 students pre-seeded, each cluster is at count 2 (waiting for 3rd student).
When a 3rd student (Charlie: 2023101003, Diana: 2023101004, etc.) explains with the
same misconception through the real model, count reaches 3 and instantly triggers
the live Brevo email alert to faculty!
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LECTURES_DATA = [
    {
        "concept_id": "oop_lecture_1",
        "fallacy_tag": "CLASS_IS_AN_OBJECT",
        "alice_text": "A class and an object are basically the same thing in memory; declaring class Car creates the car in the heap.",
        "alice_probe": "If declaring 'class Car' allocated memory on the heap, how much memory would be allocated before you ever instantiate it?",
        "bob_text": "Writing class Dog creates an actual Dog object in RAM immediately when the code runs.",
        "bob_probe": "If class Dog created an object immediately, what would new Dog() do, and how many dogs exist before writing new?",
        "remediation": "Pedagogical Intervention:\n  Writing class Dog defines what a Dog looks like. No Dog exists in memory until you write new Dog(). How many Dogs exist after class Dog alone? Zero.\nKey Takeaway: A class occupies no runtime memory for instances until instantiated.",
    },
    {
        "concept_id": "oop_lecture_2",
        "fallacy_tag": "PRIVATE_MEMBERS_INHERITED",
        "alice_text": "Since Dog extends Animal, Dog can access Animal's private fields directly without getters.",
        "alice_probe": "If private members were accessible in subclasses, the private keyword would provide no encapsulation. Can child source code name them directly?",
        "bob_text": "Subclasses inherit everything including private variables, so child class methods can modify private parent variables directly.",
        "bob_probe": "The private fields exist in the child object's memory layout, but can the child code refer to them by name?",
        "remediation": "Pedagogical Intervention:\n  If private members were accessible in subclasses, any subclass could break internal parent state. Subclasses must use parent getters/setters.\nKey Takeaway: Private fields exist in instance memory but are not directly accessible by subclass identifier.",
    },
    {
        "concept_id": "oop_lecture_3",
        "fallacy_tag": "INHERITANCE_IS_CODE_REUSE_ONLY",
        "alice_text": "I use inheritance whenever two classes share common utility methods just to avoid copying code.",
        "alice_probe": "If Stack extends ArrayList just to reuse add(), what happens when a client calls get(0) on your Stack? Does that violate LIFO?",
        "bob_text": "Inheritance is primarily a shortcut for code reuse between classes so we don't rewrite functions.",
        "bob_probe": "Would you say a Car IS-A Engine, or does a Car HAS-A Engine? When should composition be preferred?",
        "remediation": "Pedagogical Intervention:\n  Inheritance models an IS-A relationship and enforces the Liskov Substitution Principle. Use composition for code reuse without semantic taxonomy.\nKey Takeaway: Favour composition over inheritance for non-is-a relationships.",
    },
    {
        "concept_id": "oop_lecture_4",
        "fallacy_tag": "OVERLOADING_EQUALS_OVERRIDING",
        "alice_text": "When I define add(int a) and add(double a) in the same class with different parameters, that is method overriding.",
        "alice_probe": "Overriding replaces a parent method in a subclass at runtime. Is add(int) vs add(double) in the same class decided by the compiler or at runtime?",
        "bob_text": "Overloading and overriding are essentially the same polymorphism mechanism, just with different argument types.",
        "bob_probe": "Which one requires an inheritance relationship between classes, and which one happens within a single class?",
        "remediation": "Pedagogical Intervention:\n  Overloading is compile-time (static) method signature resolution in the same class. Overriding is runtime (dynamic) method dispatch in a subclass hierarchy.\nKey Takeaway: Overloading is compile-time; Overriding is runtime polymorphic dispatch.",
    },
]


def seed_cohort(students_dir: Path | None = None, telemetry_path: Path | None = None) -> None:
    s_dir = students_dir or (ROOT / "data" / "students")
    t_path = telemetry_path or (ROOT / "data" / "batch_telemetry.json")

    s_dir.mkdir(parents=True, exist_ok=True)
    t_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing student records
    for f in s_dir.glob("*.json"):
        f.unlink(missing_ok=True)

    clusters_payload = {}

    for item in LECTURES_DATA:
        cid = item["concept_id"]
        tag = item["fallacy_tag"]

        # Alice (2023101001)
        alice_rec = {
            "student_id": "2023101001",
            "concept_id": cid,
            "iteration_count": 1,
            "initial_text": item["alice_text"],
            "probes_issued": [item["alice_probe"]],
            "student_revisions": [],
            "final_verdict": "UNRESOLVED_ESCALATE",
            "tagged_fallacy": tag,
        }
        alice_json = json.dumps(alice_rec, indent=2)
        if cid == "oop_lecture_1":
            (s_dir / "2023101001.json").write_text(alice_json, encoding="utf-8")
        else:
            (s_dir / f"2023101001_{cid}.json").write_text(alice_json, encoding="utf-8")

        # Bob (2023101002)
        bob_rec = {
            "student_id": "2023101002",
            "concept_id": cid,
            "iteration_count": 1,
            "initial_text": item["bob_text"],
            "probes_issued": [item["bob_probe"]],
            "student_revisions": [],
            "final_verdict": "UNRESOLVED_ESCALATE",
            "tagged_fallacy": tag,
        }
        bob_json = json.dumps(bob_rec, indent=2)
        if cid == "oop_lecture_1":
            (s_dir / "2023101002.json").write_text(bob_json, encoding="utf-8")
        else:
            (s_dir / f"2023101002_{cid}.json").write_text(bob_json, encoding="utf-8")

        clusters_payload[tag] = {
            "fallacy_tag": tag,
            "occurrence_count": 2,
            "affected_student_ids": ["2023101001", "2023101002"],
            "sample_student_quotes": [
                item["alice_text"],
                item["bob_text"],
            ],
            "remediation_suggestion": item["remediation"],
        }

    telemetry_payload = {
        "timestamp": "2026-09-20T07:00:00.000000+00:00",
        "total_students_scanned": 2,
        "cluster_count": len(clusters_payload),
        "clusters": clusters_payload,
    }

    t_path.write_text(json.dumps(telemetry_payload, indent=2), encoding="utf-8")
    print(f"[OK] Successfully seeded 4 lecture misconception clusters (2 students each) in {s_dir} and {t_path}")


if __name__ == "__main__":
    seed_cohort()
