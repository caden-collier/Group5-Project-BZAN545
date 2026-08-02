"""Build an auditable draft crosswalk from legacy to migrated products.

Matches are suggestions, not silent replacements.  Every new product receives
its best and second-best legacy candidate, a score, a status, and a reason so
that ambiguous mappings remain visible for human review.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


FIELD_ALIASES = {
    "id": ("new_product_id", "product_id", "id", "sku"),
    "name": ("product_name", "item_name", "name", "product", "title"),
    "brand": ("brand", "brand_name", "manufacturer"),
    "category": ("category", "product_category", "department"),
    "subcategory": (
        "subcategory",
        "sub_category",
        "product_subcategory",
        "class",
    ),
    "description": ("description", "product_description", "details"),
    "size": ("size", "product_size", "package_size"),
    "price": (
        "base_price",
        "msrp",
        "list_price",
        "unit_price",
        "price",
        "retail_price",
    ),
    "margin": ("margin_rate", "gross_margin"),
    "launch_date": ("launch_date", "introduced_date"),
    "active": ("active", "is_active"),
}

TEXT_WEIGHTS = {
    # Names are the strongest clue, but the migrated table includes deliberate
    # renames. Stable business attributes therefore carry meaningful weight.
    "name": 0.35,
    "brand": 0.13,
    "category": 0.10,
    "subcategory": 0.10,
    "description": 0.00,
    "size": 0.00,
    "margin": 0.10,
    "launch_date": 0.17,
    "active": 0.02,
}
PRICE_WEIGHT = 0.03


@dataclass(frozen=True)
class Candidate:
    old_id: str
    score: float
    exact_name: bool
    compared_fields: tuple[str, ...]


def normalize(value: object) -> str:
    """Normalize text for comparison while retaining letters and numbers."""
    text = str(value or "").casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def parse_price(value: object) -> float | None:
    cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def text_similarity(left: object, right: object) -> float:
    left_text, right_text = normalize(left), normalize(right)
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0
    left_tokens, right_tokens = set(left_text.split()), set(right_text.split())
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(None, left_text, right_text).ratio()
    return max(jaccard, sequence)


def choose_columns(fieldnames: Iterable[str]) -> dict[str, str]:
    """Map semantic fields to the actual columns present in a source."""
    lowered = {name.casefold(): name for name in fieldnames}
    selected: dict[str, str] = {}
    for semantic_name, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                selected[semantic_name] = lowered[alias]
                break
    return selected


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError(f"No header found in {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def validate_source(
    path: Path,
    rows: list[dict[str, str]],
    columns: dict[str, str],
) -> None:
    if "id" not in columns:
        raise ValueError(f"Could not identify a product ID column in {path}")
    if "name" not in columns:
        raise ValueError(f"Could not identify a product name column in {path}")
    ids = [normalize(row[columns["id"]]) for row in rows]
    if not rows:
        raise ValueError(f"No product rows found in {path}")
    if any(not value for value in ids):
        raise ValueError(f"Blank product ID found in {path}")
    duplicates = [value for value, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate product IDs found in {path}: {duplicates[:5]}")


def score_candidate(
    old_row: dict[str, str],
    new_row: dict[str, str],
    old_columns: dict[str, str],
    new_columns: dict[str, str],
) -> Candidate:
    available_weights = 0.0
    weighted_score = 0.0
    compared: list[str] = []

    for field, weight in TEXT_WEIGHTS.items():
        if field not in old_columns or field not in new_columns:
            continue
        old_value = old_row[old_columns[field]]
        new_value = new_row[new_columns[field]]
        if not normalize(old_value) or not normalize(new_value):
            continue
        available_weights += weight
        weighted_score += weight * text_similarity(old_value, new_value)
        compared.append(field)

    if "price" in old_columns and "price" in new_columns:
        old_price = parse_price(old_row[old_columns["price"]])
        new_price = parse_price(new_row[new_columns["price"]])
        if old_price is not None and new_price is not None:
            available_weights += PRICE_WEIGHT
            denominator = max(old_price, new_price, 1.0)
            weighted_score += PRICE_WEIGHT * max(
                0.0, 1.0 - abs(old_price - new_price) / denominator
            )
            compared.append("price")

    score = weighted_score / available_weights if available_weights else 0.0
    old_id = old_row[old_columns["id"]]
    exact_name = (
        normalize(old_row[old_columns["name"]]).replace(" ", "")
        == normalize(new_row[new_columns["name"]]).replace(" ", "")
    )
    return Candidate(old_id, score, exact_name, tuple(compared))


def classify(best: Candidate, second: Candidate | None) -> tuple[str, str]:
    margin = best.score - (second.score if second else 0.0)
    if best.exact_name:
        return "matched_exact", "Normalized product name matches exactly."
    if best.score >= 0.90 and margin >= 0.10:
        return (
            "matched_high_confidence",
            "Strong multi-field similarity with clear separation from runner-up.",
        )
    if best.score >= 0.70 and margin < 0.10:
        return (
            "review_ambiguous",
            "Top candidates are too close; human confirmation is required.",
        )
    if best.score >= 0.70:
        return (
            "review_low_confidence",
            "Best candidate is plausible but below the automatic-match threshold.",
        )
    return "unmatched", "No sufficiently similar legacy product was found."


def build_crosswalk(
    old_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    old_columns: dict[str, str],
    new_columns: dict[str, str],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for new_row in new_rows:
        candidates = sorted(
            (
                score_candidate(
                    old_row, new_row, old_columns, new_columns
                )
                for old_row in old_rows
            ),
            key=lambda candidate: (-candidate.score, candidate.old_id),
        )
        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        status, reason = classify(best, second)
        output.append(
            {
                "new_product_id": new_row[new_columns["id"]],
                "new_product_name": new_row[new_columns["name"]],
                "proposed_legacy_product_id": best.old_id,
                "match_status": status,
                "match_score": f"{best.score:.4f}",
                "runner_up_legacy_product_id": second.old_id if second else "",
                "runner_up_score": f"{second.score:.4f}" if second else "",
                "score_margin": (
                    f"{best.score - second.score:.4f}" if second else ""
                ),
                "compared_fields": "|".join(best.compared_fields),
                "review_note": reason,
            }
        )

    # A repeated proposed legacy ID may represent a split, duplicate, or bad
    # match. Include plausible review candidates so deliberate "Alt" products
    # cannot slip through as independent matches.
    proposed = defaultdict(list)
    for row in output:
        if float(row["match_score"]) >= 0.60:
            proposed[row["proposed_legacy_product_id"]].append(row)
    for old_id, rows in proposed.items():
        if len(rows) > 1:
            for row in rows:
                row["match_status"] = "review_duplicate_candidate"
                row["review_note"] = (
                    f"Legacy product {old_id} is proposed for multiple new "
                    "products; possible split or collision."
                )
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def source_profile(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
    selected: dict[str, str],
) -> dict[str, object]:
    return {
        "path": path.as_posix(),
        "row_count": len(rows),
        "column_count": len(fieldnames),
        "columns": fieldnames,
        "semantic_columns_used": selected,
    }


def changed_vocabularies(
    old_rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    old_columns: dict[str, str],
    new_columns: dict[str, str],
) -> dict[str, dict[str, list[str]]]:
    """Report observed value changes in comparable descriptive fields."""
    output: dict[str, dict[str, list[str]]] = {}
    for field in ("brand", "category", "subcategory"):
        if field not in old_columns or field not in new_columns:
            continue
        old_values = {row[old_columns[field]] for row in old_rows}
        new_values = {row[new_columns[field]] for row in new_rows}
        removed = sorted(old_values - new_values)
        added = sorted(new_values - old_values)
        if removed or added:
            output[field] = {
                "legacy_only_values": removed,
                "new_only_values": added,
            }
    return output


def markdown_cell(value: object) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def write_report(
    path: Path,
    summary: dict[str, object],
    crosswalk: list[dict[str, str]],
) -> None:
    """Create a concise, Canvas-ready milestone response from actual outputs."""
    legacy = summary["legacy_source"]
    migrated = summary["new_source"]
    schema = summary["schema_changes"]
    status_counts = summary["status_counts"]
    duplicate_cases = [
        row
        for row in crosswalk
        if row["match_status"] == "review_duplicate_candidate"
    ]
    unresolved = [
        row
        for row in crosswalk
        if not row["match_status"].startswith("matched")
    ]
    sample = crosswalk[:5]

    lines = [
        "# Milestone 06 - Product Migration Response",
        "",
        "## Source and schema changes",
        "",
        (
            f"We loaded `{legacy['path']}` ({legacy['row_count']} rows) and "
            f"`{migrated['path']}` ({migrated['row_count']} rows). The daily "
            "orders feed also changed its join key from `product_id` through "
            "2026-07-27 to `new_product_id` beginning 2026-07-28."
        ),
        "",
        f"- Columns removed/renamed from the legacy table: "
        f"`{', '.join(schema['removed_columns']) or 'none'}`",
        f"- Columns added in the migrated table: "
        f"`{', '.join(schema['added_columns']) or 'none'}`",
        f"- Columns retained in both tables: "
        f"`{', '.join(schema['shared_columns']) or 'none'}`",
    ]
    value_changes = summary.get("value_changes", {})
    if value_changes:
        lines.extend(["", "Observed descriptive-value changes include:"])
        for field, changes in value_changes.items():
            lines.append(
                f"- `{field}` legacy-only values: "
                f"`{', '.join(changes['legacy_only_values']) or 'none'}`; "
                f"new-only values: "
                f"`{', '.join(changes['new_only_values']) or 'none'}`"
            )
    lines.extend(
        [
            "",
            "## Draft crosswalk sample",
            "",
            "| New ID | New product | Proposed legacy ID | Status | Score |",
            "|---|---|---|---|---:|",
        ]
    )
    for row in sample:
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(row[column])
                for column in (
                    "new_product_id",
                    "new_product_name",
                    "proposed_legacy_product_id",
                    "match_status",
                    "match_score",
                )
            )
            + " |"
        )

    lines.extend(["", "## Match progress", ""])
    for status, count in status_counts.items():
        lines.append(f"- `{status}`: {count}")
    lines.extend(
        [
            "",
            "## Ambiguous or unresolved decision",
            "",
        ]
    )
    if duplicate_cases:
        example = duplicate_cases[0]
        same_candidate = [
            row
            for row in duplicate_cases
            if row["proposed_legacy_product_id"]
            == example["proposed_legacy_product_id"]
        ]
        new_products = ", ".join(
            f"`{row['new_product_id']}` ({row['new_product_name']})"
            for row in same_candidate
        )
        lines.append(
            f"{new_products} both propose legacy product "
            f"`{example['proposed_legacy_product_id']}`. This could represent "
            "a deliberate product split, an alternate SKU, or a duplicate. "
            "We are keeping both rows in `review_duplicate_candidate` until "
            "the business rule for allocating historical sales is confirmed."
        )
    elif unresolved:
        example = unresolved[0]
        lines.append(
            f"`{example['new_product_id']}` ({example['new_product_name']}) "
            f"is currently `{example['match_status']}`. The leading candidate "
            f"is `{example['proposed_legacy_product_id']}` at "
            f"{example['match_score']}, while `{example['runner_up_legacy_product_id']}` "
            f"scores {example['runner_up_score']}. {example['review_note']} "
            "We are leaving this mapping unresolved rather than forcing a join "
            "that could misattribute historical sales."
        )
    else:
        lines.append(
            "No unresolved rows remain in the current draft. We will retain "
            "the scores and review notes as an audit trail."
        )
    lines.extend(
        [
            "",
            "## Repository paths",
            "",
            "- Crosswalk: `data/processed/product_crosswalk.csv`",
            "- Counts/schema summary: "
            "`data/processed/product_crosswalk_summary.json`",
            "- Source export: `src/export_product_sources.py`",
            "- Crosswalk builder: `src/build_product_crosswalk.py`",
            "- Migration-aware order ingestion: `src/preserve_daily_orders.py`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy_products", type=Path)
    parser.add_argument("new_products", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/product_crosswalk.csv"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/processed/product_crosswalk_summary.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/milestones/milestone_06/Canvas_Submission.md"),
    )
    args = parser.parse_args()

    old_rows, old_fields = read_csv(args.legacy_products)
    new_rows, new_fields = read_csv(args.new_products)
    old_columns = choose_columns(old_fields)
    new_columns = choose_columns(new_fields)
    validate_source(args.legacy_products, old_rows, old_columns)
    validate_source(args.new_products, new_rows, new_columns)

    crosswalk = build_crosswalk(
        old_rows, new_rows, old_columns, new_columns
    )
    write_csv(args.output, crosswalk)

    summary = {
        "legacy_source": source_profile(
            args.legacy_products, old_rows, old_fields, old_columns
        ),
        "new_source": source_profile(
            args.new_products, new_rows, new_fields, new_columns
        ),
        "schema_changes": {
            "removed_columns": sorted(set(old_fields) - set(new_fields)),
            "added_columns": sorted(set(new_fields) - set(old_fields)),
            "shared_columns": sorted(set(old_fields) & set(new_fields)),
        },
        "value_changes": changed_vocabularies(
            old_rows, new_rows, old_columns, new_columns
        ),
        "crosswalk_row_count": len(crosswalk),
        "status_counts": dict(
            sorted(Counter(row["match_status"] for row in crosswalk).items())
        ),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_report(args.report, summary, crosswalk)

    print(f"Crosswalk: {args.output.as_posix()} ({len(crosswalk)} rows)")
    print(f"Summary: {args.summary.as_posix()}")
    print(f"Canvas response: {args.report.as_posix()}")
    for status, count in summary["status_counts"].items():
        print(f"{status}: {count}")


if __name__ == "__main__":
    main()
