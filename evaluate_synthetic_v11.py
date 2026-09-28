"""Reproducible, AI-authored synthetic evaluation; labels were frozen first.

Do not edit the dataset, model, or thresholds after inspecting these results
and continue to present this as an independent test. A future human sample
would require fresh cases labeled before anyone runs the model on them.
"""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from sklearn.metrics import accuracy_score, f1_score

from handoff_store import TicketStore
from intent import baseline, learned, make_model
from intent_data import HOLDOUT, TRAIN
from service import (CaseRepository, Conversation, SessionAuthority,
                     create_handoff_ticket, respond)


HERE = Path(__file__).parent
CASES = HERE / "synthetic_eval_cases_v11.json"
OUTPUT = HERE / "synthetic_eval_results_v11.json"
FROZEN_SHA256 = "cf274e0fd14fcd33c1d9cce940727dd4a81635436e82f321984226c0c84b51ea"


def pct(values, percentile):
    ordered = sorted(values)
    return round(ordered[int((len(ordered) - 1) * percentile)], 2)


def load_cases():
    raw = CASES.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != FROZEN_SHA256:
        raise ValueError("Evaluation set changed after labels were frozen; use a new version")
    cases = json.loads(raw)
    training = {t.casefold() for group in TRAIN.values() for examples in group.values() for t in examples}
    previous = {text.casefold() for _, _, text in HOLDOUT}
    all_cases = cases["intent_cases"] + cases["workflow_cases"]
    if len(all_cases) != 58 or len({c["id"] for c in all_cases}) != 58:
        raise ValueError("Missing or duplicated evaluation case")
    if any(c["text"].casefold() in training | previous for c in all_cases):
        raise ValueError("Exact overlap with development sets")
    return cases, digest


def test_intents(cases, model):
    labels = [case["expected"] for case in cases]
    results = {}
    for name, classifier in (("rules", baseline), ("learned", lambda t: learned(t, model))):
        predicted = [classifier(case["text"]) for case in cases]
        by_lang = {}
        for language in ("es", "pt"):
            selected = [(c, p) for c, p in zip(cases, predicted) if c["lang"] == language]
            by_lang[language] = {
                "n": len(selected),
                "correct": sum(c["expected"] == p for c, p in selected),
                "abstained": sum(p == "unclear" for _, p in selected),
            }
        results[name] = {
            "n": len(cases),
            "correct": sum(a == b for a, b in zip(labels, predicted)),
            "accuracy": round(accuracy_score(labels, predicted), 3),
            "macro_f1": round(f1_score(labels, predicted,
                                        labels=["status", "new_dispute", "human", "other"],
                                        average="macro", zero_division=0), 3),
            "abstained": sum(p == "unclear" for p in predicted),
            "by_language": by_lang,
            "errors": [{"id": c["id"], "expected": c["expected"], "actual": p}
                       for c, p in zip(cases, predicted) if c["expected"] != p],
        }
    return results


def safe_without_case(reply):
    return (reply.kind != "resolved" and not reply.evidence and
            not reply.case_view and
            not (reply.handoff and reply.handoff.get("verified_status")))


def test_workflow(cases, model):
    authority = SessionAuthority(b"synthetic-eval-frozen-secret-2026")
    repository = CaseRepository()
    results = {}
    with TemporaryDirectory() as directory:
        for router in ("baseline", "learned"):
            tickets = TicketStore(Path(directory) / f"{router}.sqlite3")
            issues, times, outcomes = [], [], Counter()
            by_language = {"es": Counter(), "pt": Counter()}
            unsafe = 0
            confirmed_tickets = 0
            for case in cases:
                now = 1700000000
                name, pin = (("Alicia (prueba)", "1379") if case["actor"] == "a"
                             else ("Bruno (prueba)", "2468"))
                token = authority.issue(name, pin, now=now,
                                        ttl=1 if case.get("expired") else 600)
                if case.get("tamper"):
                    token = token[:-1] + ("0" if token[-1] != "0" else "1")
                conversation = Conversation()
                start = time.perf_counter()
                reply = respond(case["text"], token, conversation, authority,
                                repository, model, language=case["lang"],
                                router=router, now=now + 2,
                                fail_tool=case.get("fail_tool", False))
                if case.get("then") and reply.kind == "clarify":
                    reply = respond(case["then"], token, conversation, authority,
                                    repository, model, language=case["lang"],
                                    router=router, now=now + 2)
                ticket = None
                if case["expected"] == "handoff" and reply.kind == "handoff":
                    ticket = create_handoff_ticket(
                        token, conversation, authority, repository, tickets,
                        language=case["lang"], now=now + 2,
                    )
                    confirmed_tickets += ticket.kind == "created"
                times.append((time.perf_counter() - start) * 1000)
                outcomes[reply.kind] += 1
                expected = case["expected"]
                if expected == "handoff":
                    correct = ticket is not None and ticket.kind == "created"
                elif expected in ("denied", "auth_required", "clarify", "unsupported", "resolved"):
                    correct = reply.kind == expected
                    if expected in ("denied", "auth_required"):
                        correct = correct and safe_without_case(reply)
                elif expected == "safe_nondisclosure":
                    correct = safe_without_case(reply)
                elif expected == "safe_tool_failure":
                    correct = safe_without_case(reply) and reply.kind in (
                        "handoff", "unavailable", "unsupported", "clarify")
                else:
                    raise ValueError(f"Unsupported expected outcome: {expected}")
                by_language[case["lang"]]["n"] += 1
                by_language[case["lang"]]["correct"] += bool(correct)
                if expected in ("denied", "auth_required", "safe_nondisclosure", "safe_tool_failure"):
                    unsafe += not safe_without_case(reply)
                if not correct:
                    issues.append({"id": case["id"], "expected": expected,
                                   "actual": reply.kind,
                                   "ticket": ticket.kind if ticket else None})
            results[router] = {
                "n": len(cases), "correct": len(cases) - len(issues),
                "by_language": {k: dict(v) for k, v in by_language.items()},
                "outcomes": dict(outcomes), "ticket_created_and_read": confirmed_tickets,
                "unsafe_disclosures_or_actions_detected": unsafe,
                "p50_local_ms": pct(times, 0.50), "p95_local_ms": pct(times, 0.95),
                "errors": issues,
            }
    return results


def evaluate():
    cases, digest = load_cases()
    model = make_model()
    return {
        "kind": "fresh AI-authored synthetic stress test; not blind or independently collected human data",
        "created": "2026-09-27",
        "frozen_labels_sha256": digest,
        "model_unchanged_after_frozen_labels": True,
        "intents": test_intents(cases["intent_cases"], model),
        "workflow": test_workflow(cases["workflow_cases"], model),
        "scope": "Local in-process simulation with fictitious cases, public test identities, and temporary SQLite tickets. No real customer, human recipient, or bank action.",
        "cost": "External model/API requests: 0. Hosting cost not measured. Local p50/p95 exclude network, browser, human click, concurrency and cold start.",
        "caveat": "One AI authored all labels with knowledge of the task. Exact-string separation from training and prior evaluation does not prevent semantic overlap or prove performance on real users. Mistakes and abstentions count as misses for strict accuracy; evaluate on new human-labeled cases later.",
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(evaluate(), ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Wrote {OUTPUT}")
