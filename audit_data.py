"""Read original organizer ZIPs and emit only aggregate evidence; no records exported.

Usage: python audit_data.py --interactions path.zip --complaints path.zip --transcripts path.zip
"""

import argparse
from collections import Counter, defaultdict
import csv
import io
import json
import zipfile


def rows(path):
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if name.lower().endswith(".csv"):
                with archive.open(name) as binary:
                    reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
                    yield from reader


def audit(interactions, complaints, transcripts):
    interactions_by_id = {}
    categories = Counter()
    followups = Counter()
    for row in rows(interactions):
        key = row["interaction_id"]
        if key in interactions_by_id:
            raise ValueError("Duplicate interaction_id")
        interactions_by_id[key] = (row["customer_id"], row["reason_category"])
        categories[row["reason_category"]] += 1
        if row["requires_followup"].lower() == "true":
            followups[row["reason_category"]] += 1
    complaints_seen = set()
    subcategories, statuses = Counter(), Counter()
    missing_origin = 0
    for row in rows(complaints):
        key = row["complaint_id"]
        if key in complaints_seen:
            raise ValueError("Duplicate complaint_id")
        complaints_seen.add(key)
        subcategories[row["subcategory"] or "Sin dato"] += 1
        statuses[row["status"]] += 1
        missing_origin += not bool(row["origin_interaction_id"])
    transcript_ids, texts = set(), set()
    text_to_topics = defaultdict(set)
    text_frequency = Counter()
    transcript_topics, topic_mismatch = Counter(), 0
    unjoined, wrong_customer, balance_mentions, charge_mentions = 0, 0, 0, 0
    for row in rows(transcripts):
        key = row["transcript_id"]
        if key in transcript_ids:
            raise ValueError("Duplicate transcript_id")
        transcript_ids.add(key)
        text = row["customer_text"]
        texts.add(text)
        text_to_topics[text].add(row["main_topics"])
        text_frequency[text] += 1
        balance_mentions += "saldo" in text.lower()
        charge_mentions += "cargo no reconocido" in text.lower()
        matched = interactions_by_id.get(row["interaction_id"])
        unjoined += matched is None
        if matched:
            wrong_customer += matched[0] != row["customer_id"]
            topic_mismatch += matched[1] != row["main_topics"]
        transcript_topics[row["main_topics"]] += 1
    return {
        "provenance": "organizer ZIPs; read locally; aggregate outputs only",
        "interactions_2025": {"rows": len(interactions_by_id), "by_reason_category": dict(categories),
                              "requires_followup_by_reason": dict(followups)},
        "complaints_2025": {"rows": len(complaints_seen), "missing_origin_interaction_id": missing_origin,
                            "by_subcategory": dict(subcategories), "by_status": dict(statuses)},
        "transcripts_jan_2025": {"rows": len(transcript_ids), "distinct_customer_texts": len(texts),
                                 "customer_text_mentions_saldo": balance_mentions,
                                 "customer_text_mentions_unrecognized_charge": charge_mentions,
                                 "distinct_texts_used_across_multiple_topics":
                                     sum(len(topics) > 1 for topics in text_to_topics.values()),
                                 "two_most_frequent_texts_count": sum(n for _, n in text_frequency.most_common(2)),
                                 "unjoined_to_interactions": unjoined,
                                 "customer_id_mismatch": wrong_customer,
                                 "topic_vs_interaction_category_mismatch": topic_mismatch,
                                 "by_main_topic": dict(transcript_topics)},
        "interpretation": "Transcript texts have very low variety and repeat across reason labels; do not train an intent classifier on these labels.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interactions", required=True)
    parser.add_argument("--complaints", required=True)
    parser.add_argument("--transcripts", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.interactions, args.complaints, args.transcripts), ensure_ascii=False, indent=2))
