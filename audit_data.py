"""Aggregate synthetic LATAM Bank CSV/ZIP tables and export evidence + two PNG charts.

Usage from this directory:
  python audit_data.py --interactions ../interacciones_2025_extraidas \
    --complaints ../upload/quejas_2025.zip \
    --transcripts ../upload/transcripciones_2025_01.zip

Country requires an explicit country field or an optional --customers source.
Scenario ROI needs six explicit assumptions; no real costs or LLM successes are
recorded in these three tables. No row-level text or identifiers are exported.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import io
import json
import math
from pathlib import Path
from typing import Iterator
from zipfile import BadZipFile, ZipFile


TABLES = {"interactions": "call_center_interactions", "complaints": "complaints",
          "transcripts": "call_transcripts", "customers": "customers"}
RESOLVED = {"Resolved", "Closed"}
ROI_FORMULAS = {
    "attempts": "complaint_related_interactions * automatable_share (rounded to nearest whole interaction)",
    "automated_resolutions": "attempts * automation_success_rate",
    "new_cost": "attempts * llm_cost_per_attempt + failed_attempts * human_cost + fixed_platform_cost",
    "net_savings": "baseline_human_cost - new_cost",
    "agent_hours_freed": "automated_resolutions * human_handling_minutes / 60",
}


def rows(location: str | Path, table: str) -> Iterator[dict[str, str]]:
    """Stream only CSV members for this table, without extracting the ZIP."""
    path, name = Path(location), TABLES[table]
    if not path.exists():
        raise FileNotFoundError(f"Missing {table} source: {path}")
    if path.is_file() and path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as file:
            yield from csv.DictReader(file)
    elif path.is_dir():
        matches = sorted(p for p in path.rglob("*.csv") if name in p.name.casefold())
        if not matches:
            raise ValueError(f"No {name} CSVs in {path}")
        for member in matches:
            with member.open(encoding="utf-8-sig", newline="") as file:
                yield from csv.DictReader(file)
    elif path.suffix.lower() == ".zip":
        try:
            with ZipFile(path) as archive:
                matches = sorted(n for n in archive.namelist()
                                 if n.lower().endswith(".csv") and
                                 name in n.replace("\\", "/").rsplit("/", 1)[-1].casefold())
                if not matches:
                    raise ValueError(f"No {name} CSVs in {path.name}")
                for member in matches:
                    with archive.open(member) as binary:
                        with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as file:
                            yield from csv.DictReader(file)
        except BadZipFile as error:
            raise ValueError(f"Corrupt {path.name}; use a complete ZIP or extracted directory") from error
    else:
        raise ValueError(f"Expected CSV, ZIP or directory: {path}")


def label(value: str | None) -> str:
    return (value or "").strip() or "Sin dato"


def parse_bool(value: str | None) -> bool | None:
    text = (value or "").strip().casefold()
    if text in {"true", "1", "yes", "sí", "sim"}:
        return True
    if text in {"false", "0", "no", "não", "nao"}:
        return False
    if not text:
        return None
    raise ValueError(f"Invalid boolean: {text[:32]!r}")


def percent(part: int | float, total: int | float) -> float | None:
    return round(100 * part / total, 2) if total else None


def fcr_add(bucket: Counter, resolved: bool | None, followup: bool | None) -> None:
    bucket["n"] += 1
    if resolved is not None:
        bucket["known"] += 1
        bucket["fcr"] += resolved is True
        bucket["strict"] += resolved is True and followup is False


def fcr_group(name: str, bucket: Counter) -> dict:
    return {"group": name, "interactions_n": bucket["n"], "known_fcr_n": bucket["known"],
            "fcr_n": bucket["fcr"], "fcr_rate_pct": percent(bucket["fcr"], bucket["known"]),
            "strict_without_followup_n": bucket["strict"],
            "strict_without_followup_rate_pct": percent(bucket["strict"], bucket["known"])}


def resolution_time(row: dict[str, str]) -> tuple[float | None, str | None]:
    days = (row.get("resolution_days") or "").strip()
    if days:
        try:
            value = float(days)
        except ValueError:
            value = float("nan")
        if math.isfinite(value) and value >= 0:
            return value, "reported"
    creation, resolved = (row.get("creation_date") or "").strip(), (row.get("resolution_date") or "").strip()
    if creation and resolved:
        try:
            value = (datetime.fromisoformat(resolved) - datetime.fromisoformat(creation)).total_seconds() / 86400
            return (value, "derived") if value >= 0 else (None, "invalid")
        except ValueError:
            return None, "invalid"
    return None, "invalid" if days else None


def resolution_group(name: str, bucket: Counter) -> dict:
    n = bucket["timed"]
    return {"group": name, "resolved_cases_n": bucket["resolved"], "timed_cases_n": n,
            "mean_days": round(bucket["days"] / n, 2) if n else None,
            "reported_days_n": bucket["reported"], "derived_from_dates_n": bucket["derived"],
            "without_valid_time_n": bucket["resolved"] - n}


def load_countries(path: str | Path | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if path is not None:
        for row in rows(path, "customers"):
            key, country = (row.get("customer_id") or "").strip(), (row.get("country") or "").strip()
            if key and country:
                if key in result and result[key] != country:
                    raise ValueError("Contradictory country for customer_id")
                result[key] = country
    return result


@dataclass(frozen=True)
class Scenario:
    human_cost_usd: float
    llm_cost_per_attempt_usd: float
    automatable_share: float
    automation_success_rate: float
    human_handling_minutes: float
    fixed_platform_cost_usd: float

    def validate(self) -> None:
        if any(not math.isfinite(n) or n < 0 for n in (
                self.human_cost_usd, self.llm_cost_per_attempt_usd,
                self.human_handling_minutes, self.fixed_platform_cost_usd)):
            raise ValueError("Costs and handling minutes must be finite and nonnegative")
        if any(not math.isfinite(n) or not 0 <= n <= 1 for n in (
                self.automatable_share, self.automation_success_rate)):
            raise ValueError("Shares and success rates must be between zero and one")


def roi(volume: int, scenario: Scenario | None) -> dict:
    if scenario is None:
        return {"status": "not_calculable_without_explicit_assumptions",
                "sampled_complaint_related_interactions_n": volume,
                "human_cost_per_interaction_usd": None,
                "llm_cost_per_automated_resolution_usd": None,
                "savings_pct": None, "agent_hours_freed": None, "roi_pct": None,
                "formulas": ROI_FORMULAS,
                "required_inputs": list(Scenario.__dataclass_fields__),
                "reason": "No costs or LLM success outcomes in these tables; FCR is not an automation success rate."}
    scenario.validate()
    attempts = round(volume * scenario.automatable_share)
    automated = round(attempts * scenario.automation_success_rate)
    baseline = attempts * scenario.human_cost_usd
    llm_spend = attempts * scenario.llm_cost_per_attempt_usd
    investment = llm_spend + scenario.fixed_platform_cost_usd
    proposed = investment + (attempts - automated) * scenario.human_cost_usd
    savings = baseline - proposed
    return {"status": "assumption_based_scenario_not_observed_savings",
            "volume_scope": "supplied complaint-related interaction count multiplied by assumed automatable share",
            "assumptions": asdict(scenario), "sampled_complaint_related_interactions_n": volume,
            "llm_attempts_n": attempts, "automated_resolutions_n": automated,
            "attempts_requiring_human_after_failure_n": attempts - automated,
            "human_cost_per_interaction_usd": scenario.human_cost_usd,
            "llm_cost_per_automated_resolution_usd": round(llm_spend / automated, 4) if automated else None,
            "llm_unit_cost_definition": "total LLM attempt cost divided by automated successes; excludes retries handled by humans and fixed platform cost",
            "baseline_cost_usd": round(baseline, 2), "proposed_cost_usd": round(proposed, 2),
            "llm_spend_usd": round(llm_spend, 2), "net_savings_usd": round(savings, 2),
            "savings_pct": percent(savings, baseline),
            "agent_hours_freed": round(automated * scenario.human_handling_minutes / 60, 2),
            "roi_pct": percent(savings, investment),
            "formulas": ROI_FORMULAS,
            "roi_definition": "(baseline human cost - new cost) / (LLM variable spend + fixed platform cost); excludes unmodeled risk and transition"}


def audit(interactions: str | Path, complaints: str | Path, transcripts: str | Path, *,
          customers: str | Path | None = None, scenario: Scenario | None = None) -> dict:
    countries = load_countries(customers)
    by_id: dict[str, tuple[str, str]] = {}
    reasons, followup_reasons = Counter(), Counter()
    overall = Counter()
    fcr_channels: dict[str, Counter] = defaultdict(Counter)
    fcr_countries: dict[str, Counter] = defaultdict(Counter)
    fcr_joint: dict[tuple[str, str], Counter] = defaultdict(Counter)
    supervisor = conflicts = unknown_interaction_country = complaint_contacts = 0
    first_date = last_date = None
    for row in rows(interactions, "interactions"):
        key = (row.get("interaction_id") or "").strip()
        if not key or key in by_id:
            raise ValueError("Missing or duplicate interaction_id")
        reason, channel = label(row.get("reason_category")), label(row.get("channel"))
        by_id[key] = ((row.get("customer_id") or "").strip(), reason)
        reasons[reason] += 1
        complaint_contacts += reason.casefold() == "queja"
        resolved, followup = parse_bool(row.get("was_resolved")), parse_bool(row.get("requires_followup"))
        supervisor += parse_bool(row.get("was_escalated")) is True
        conflicts += resolved is True and followup is True
        followup_reasons[reason] += followup is True
        for bucket in (overall, fcr_channels[channel]):
            fcr_add(bucket, resolved, followup)
        country = (row.get("country") or "").strip() or countries.get((row.get("customer_id") or "").strip())
        if country:
            fcr_add(fcr_countries[country], resolved, followup)
            fcr_add(fcr_joint[(channel, country)], resolved, followup)
        else:
            unknown_interaction_country += 1
        date = (row.get("process_date") or "").strip()
        if date:
            first_date = min(first_date, date) if first_date else date
            last_date = max(last_date, date) if last_date else date
    if not by_id:
        raise ValueError("No interactions found")

    complaint_ids: set[str] = set()
    categories, subcategories, combined, statuses = Counter(), Counter(), Counter(), Counter()
    timings = Counter()
    time_channels: dict[str, Counter] = defaultdict(Counter)
    time_countries: dict[str, Counter] = defaultdict(Counter)
    time_joint: dict[tuple[str, str], Counter] = defaultdict(Counter)
    missing_origin = unknown_complaint_country = invalid_time = 0
    for row in rows(complaints, "complaints"):
        key = (row.get("complaint_id") or "").strip()
        if not key or key in complaint_ids:
            raise ValueError("Missing or duplicate complaint_id")
        complaint_ids.add(key)
        category, sub, status = (label(row.get(k)) for k in ("category", "subcategory", "status"))
        channel = label(row.get("reception_channel"))
        categories[category] += 1
        subcategories[sub] += 1
        combined[(category, sub)] += 1
        statuses[status] += 1
        missing_origin += not bool((row.get("origin_interaction_id") or "").strip())
        country = (row.get("country") or "").strip() or countries.get((row.get("customer_id") or "").strip())
        unknown_complaint_country += not bool(country)
        if status in RESOLVED:
            buckets = [timings, time_channels[channel]]
            if country:
                buckets += [time_countries[country], time_joint[(channel, country)]]
            days, origin = resolution_time(row)
            invalid_time += origin == "invalid"
            for bucket in buckets:
                bucket["resolved"] += 1
                if days is not None:
                    bucket["timed"] += 1
                    bucket["days"] += days
                    bucket[origin] += 1
    if not complaint_ids:
        raise ValueError("No complaints found")

    transcript_ids: set[str] = set()
    text_topics: dict[str, set[str]] = defaultdict(set)
    text_frequency, topics = Counter(), Counter()
    unjoined = wrong_customer = topic_mismatch = balance_mentions = charge_mentions = 0
    for row in rows(transcripts, "transcripts"):
        key = (row.get("transcript_id") or "").strip()
        if not key or key in transcript_ids:
            raise ValueError("Missing or duplicate transcript_id")
        transcript_ids.add(key)
        text, topic = row.get("customer_text") or "", label(row.get("main_topics"))
        text_topics[text].add(topic)
        text_frequency[text] += 1
        balance_mentions += "saldo" in text.casefold()
        charge_mentions += "cargo no reconocido" in text.casefold()
        match = by_id.get((row.get("interaction_id") or "").strip())
        if match is None:
            unjoined += 1
        else:
            wrong_customer += match[0] != (row.get("customer_id") or "").strip()
            topic_mismatch += match[1] != topic
        topics[topic] += 1

    fcr_by_channel = sorted((fcr_group(n, b) for n, b in fcr_channels.items()),
                            key=lambda r: (-r["interactions_n"], r["group"]))
    time_by_channel = sorted((resolution_group(n, b) for n, b in time_channels.items()),
                             key=lambda r: (-r["resolved_cases_n"], r["group"]))
    country_available = bool(fcr_countries or time_countries)
    return {
        "provenance": {"dataset": "synthetic LATAM Bank samples", "record_level_data_exported": False,
                       "sources": {name: "directory" if Path(path).is_dir() else Path(path).suffix.lower().lstrip(".")
                                   for name, path in (("interactions", interactions), ("complaints", complaints),
                                                      ("transcripts", transcripts))},
                       "interactions_process_date_min": first_date,
                       "interactions_process_date_max": last_date},
        "interactions_2025": {
            "rows": len(by_id), "by_reason_category": dict(reasons),
            "requires_followup_by_reason": dict(followup_reasons),
            "fcr": {"definition": "was_resolved=True; documented as resolved on first call",
                    "denominator": "nonmissing was_resolved interactions", "known_fcr_n": overall["known"],
                    "resolved_first_contact_n": overall["fcr"],
                    "rate_pct": percent(overall["fcr"], overall["known"]),
                    "strict_without_followup_n": overall["strict"],
                    "strict_without_followup_rate_pct": percent(overall["strict"], overall["known"]),
                    "by_channel": fcr_by_channel,
                    "by_country": sorted((fcr_group(n, b) for n, b in fcr_countries.items()),
                                         key=lambda r: r["group"]) if fcr_countries else None,
                    "by_channel_country": sorted(({"channel": ch, "country": country,
                                                   **fcr_group(country, b)}
                                                  for (ch, country), b in fcr_joint.items()),
                                                 key=lambda r: (r["country"], r["channel"])) if fcr_joint else None,
                    "country_unknown_n": unknown_interaction_country},
            "escalated_to_supervisor": {"n": supervisor, "rate_pct": percent(supervisor, len(by_id)),
                                        "definition": "was_escalated=True means supervisor, not human handoff"}},
        "complaints_2025": {
            "rows": len(complaint_ids), "missing_origin_interaction_id": missing_origin,
            "by_category": dict(categories), "by_subcategory": dict(subcategories),
            "by_status": dict(statuses),
            "by_category_subcategory": [
                {"category": cat, "subcategory": sub, "count": n}
                for (cat, sub), n in sorted(combined.items(), key=lambda pair: (-pair[1], pair[0]))],
            "currently_escalated_status": {"n": statuses["Escalated"],
                                            "rate_pct": percent(statuses["Escalated"], len(complaint_ids)),
                                            "definition": "status snapshot, not final human outcome"},
            "final_human_escalation": {"rate_pct": None,
                "reason": "No destination or longitudinal final outcome; Escalated does not establish human support"},
            "resolution_time": {
                "unit": "days", "population": "Resolved or Closed complaints",
                "priority": "resolution_days if nonnegative, otherwise resolution_date minus creation_date",
                "overall": resolution_group("all", timings),
                "by_reception_channel": time_by_channel,
                "by_country": sorted((resolution_group(n, b) for n, b in time_countries.items()),
                                     key=lambda r: r["group"]) if time_countries else None,
                "by_reception_channel_country": sorted(({
                    "channel": ch, "country": country, **resolution_group(country, b)}
                    for (ch, country), b in time_joint.items()),
                    key=lambda r: (r["country"], r["channel"])) if time_joint else None,
                "country_unknown_n": unknown_complaint_country,
                "invalid_resolution_time_n": invalid_time}},
        "transcripts_jan_2025": {
            "rows": len(transcript_ids), "distinct_customer_texts": len(text_topics),
            "customer_text_mentions_saldo": balance_mentions,
            "customer_text_mentions_unrecognized_charge": charge_mentions,
            "distinct_texts_used_across_multiple_topics": sum(len(t) > 1 for t in text_topics.values()),
            "two_most_frequent_texts_count": sum(n for _, n in text_frequency.most_common(2)),
            "unjoined_to_interactions": unjoined, "customer_id_mismatch": wrong_customer,
            "topic_vs_interaction_category_mismatch": topic_mismatch,
            "by_main_topic": dict(topics)},
        "roi": {"contact_scope": "interactions with reason_category=Queja; not a measure of disputes eligible for automation",
                **roi(complaint_contacts, scenario)},
        "data_quality": {
            "country_available": country_available,
            "country_note": "Explicit country or customer join" if country_available else
                "Country absent from these tables; accent and currency cannot establish residence",
            "was_resolved_true_and_requires_followup_true_n": conflicts,
            "fcr_note": "Primary FCR follows the data dictionary; strict no-followup proxy is separate. Conflicting flags need review.",
            "complaint_to_interaction_linkable_n": len(complaint_ids) - missing_origin,
            "cross_table_note": "Interaction FCR and complaint resolution days use different populations; do not join by channel name."},
        "interpretation": "Repeated transcript text across labels is unsuitable for intent training. Supervisor escalation and Escalated status do not measure final human handoff.",
    }


def draw_charts(report: dict, folder: str | Path) -> tuple[Path, Path]:
    """Two presentation-sized charts; source tables and denominators stay distinct."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destination = Path(folder)
    destination.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "text.color": "#173642", "axes.labelcolor": "#294450"})
    palette = {"Transactions": "#176b5b", "Technical": "#448c83", "Fees": "#78816a",
               "Branch": "#a68957", "Service": "#5c7ba0"}
    values = list(reversed(report["complaints_2025"]["by_category_subcategory"]))
    fig, ax = plt.subplots(figsize=(13.33, 7.5), facecolor="#f8faf9")
    ax.set_facecolor("#f8faf9")
    bars = ax.barh([f'{r["category"]} · {r["subcategory"]}' for r in values],
                   [r["count"] for r in values], height=.7,
                   color=[palette.get(r["category"], "#617d83") for r in values])
    ax.bar_label(bars, labels=[f'{r["count"]:,}' for r in values], padding=7, fontsize=10)
    ax.set_xlim(0, max(r["count"] for r in values) * 1.2)
    ax.set_xlabel("Expedientes (conteo, no contactos)")
    ax.grid(axis="x", alpha=.16)
    ax.set_axisbelow(True)
    fig.suptitle("¿Dónde se concentran las reclamaciones?", x=.07, y=.982,
                 ha="left", fontsize=21, weight="bold")
    fig.text(.07, .91, f'{report["complaints_2025"]["rows"]:,} expedientes sintéticos · 2025 · categorías de la fuente',
             color="#52716f")
    country_note = ("Desglose por país disponible en JSON." if report["data_quality"]["country_available"]
                    else "País no disponible en estas tres tablas.")
    fig.text(.07, .035, f"«Sin dato» conserva faltantes. {country_note}",
             color="#61747a", fontsize=10)
    fig.subplots_adjust(left=.30, right=.94, top=.86, bottom=.14)
    first = destination / "complaints_category_subcategory.png"
    fig.savefig(first, dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)

    fcr = report["interactions_2025"]["fcr"]["by_channel"]
    resolution = report["complaints_2025"]["resolution_time"]["by_reception_channel"]
    fig, (left, right) = plt.subplots(1, 2, figsize=(13.33, 7.5), facecolor="#f8faf9")
    for ax in (left, right):
        ax.set_facecolor("#f8faf9")
        ax.grid(axis="x", alpha=.17)
        ax.set_axisbelow(True)
    fcr_order = sorted(fcr, key=lambda r: r["fcr_rate_pct"] or 0)
    bars = left.barh([r["group"] for r in fcr_order],
                     [r["fcr_rate_pct"] or 0 for r in fcr_order], height=.65, color="#176b5b")
    left.bar_label(bars, labels=[f'{r["fcr_rate_pct"]:.1f}% (n={r["known_fcr_n"]:,})'
                                 if r["fcr_rate_pct"] is not None else "Sin dato"
                                 for r in fcr_order], padding=6, fontsize=9)
    left.set_xlim(0, 100)
    left.set_xlabel("FCR reportado (%)")
    left.set_title("Interacciones · FCR", loc="left", fontsize=13, pad=18)
    timed = sorted((r for r in resolution if r["mean_days"] is not None),
                   key=lambda r: r["mean_days"])
    bars = right.barh([r["group"] for r in timed], [r["mean_days"] for r in timed],
                      height=.65, color="#5c7ba0")
    right.bar_label(bars, labels=[f'{r["mean_days"]:.1f} d (n={r["timed_cases_n"]:,})'
                                  for r in timed], padding=6, fontsize=9)
    right.set_xlim(0, max((r["mean_days"] for r in timed), default=1) * 1.38)
    right.set_xlabel("Días promedio, casos resueltos con tiempo válido")
    right.set_title("Reclamaciones · días hasta resolver", loc="left", fontsize=13, pad=18)
    fig.suptitle("Desempeño operativo por canal", x=.05, y=.982, ha="left", fontsize=21, weight="bold")
    fig.text(.05, .91, "Dos poblaciones distintas: no combinar FCR de interacciones con días de reclamaciones.",
             color="#52716f")
    escalated = report["complaints_2025"]["currently_escalated_status"]["rate_pct"]
    supervisor = report["interactions_2025"]["escalated_to_supervisor"]["rate_pct"]
    fig.text(.05, .04, f'Supervisor: {supervisor}% de interacciones · Estado Escalated: {escalated}% de reclamaciones (no destino final).',
             color="#61747a", fontsize=9)
    fig.subplots_adjust(left=.10, right=.94, top=.83, bottom=.17, wspace=.45)
    second = destination / "service_outcomes_by_channel.png"
    fig.savefig(second, dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)
    return first, second


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for table in ("interactions", "complaints", "transcripts"):
        parser.add_argument(f"--{table}", required=True, help="CSV, ZIP or extracted directory")
    parser.add_argument("--customers", help="Optional customer_id,country source; records not exported")
    parser.add_argument("--output", type=Path, default=Path("analysis_evidence.json"))
    parser.add_argument("--charts-dir", type=Path, default=Path("figures"))
    for name in Scenario.__dataclass_fields__:
        parser.add_argument("--" + name.replace("_", "-"), type=float)
    args = parser.parse_args()
    assumptions = tuple(getattr(args, name) for name in Scenario.__dataclass_fields__)
    if any(value is not None for value in assumptions) and not all(value is not None for value in assumptions):
        parser.error("ROI scenario requires all six explicit assumptions")
    report = audit(args.interactions, args.complaints, args.transcripts, customers=args.customers,
                   scenario=Scenario(*assumptions) if all(value is not None for value in assumptions) else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    first, second = draw_charts(report, args.charts_dir)
    print(f"Saved {args.output}, {first}, {second}")


if __name__ == "__main__":
    main()
