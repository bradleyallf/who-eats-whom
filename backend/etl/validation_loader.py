"""
ETL loader for full dataset - reads results_crop.csv and loads
flagged records into validation_queue in PostgreSQL.

Flagging rule: Falsely identified = No Match
This matches the pipeline's actual accuracy metric (71.93% correct)
giving ~28% flagged records (~6,963 of 24,803 images)

Photo URLs are constructed from photo_id extracted from image_id.
Format: obs_{observation_id}_photo_{photo_id}
URL: https://inaturalist-open-data.s3.amazonaws.com/photos/{photo_id}/medium.jpeg

Usage:
  python3 -m backend.etl.validation_loader \
    --results /path/to/results_crop.csv \
    --dsn postgresql://whodba:whopass@localhost:5433/who_eats_whom
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load full BioVerify dataset flagged records into validation_queue."
    )
    parser.add_argument(
        "--results", type=Path, required=True,
        help="Path to results_crop.csv"
    )
    parser.add_argument(
        "--dsn", required=True,
        help="Postgres connection string."
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, Any]]:
    """Read CSV into list of row dictionaries."""
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))


def extract_photo_id(image_id: str) -> Optional[str]:
    """
    Extract photo_id from image_id.
    image_id format: obs_102691691_photo_171703626
    Returns: 171703626
    """
    try:
        clean = image_id.split("_box")[0]
        return clean.split("_photo_")[1]
    except (IndexError, AttributeError):
        return None


def extract_observation_id(image_id: str) -> Optional[str]:
    """
    Extract observation_id from image_id.
    image_id format: obs_102691691_photo_171703626
    Returns: 102691691
    """
    try:
        return image_id.split("_photo_")[0].replace("obs_", "")
    except (IndexError, AttributeError):
        return None


def construct_photo_url(photo_id: str) -> str:
    """
    Construct iNaturalist S3 URL from photo_id.
    Uses medium.jpeg - same source Surabhi used in pipeline.
    """
    return f"https://inaturalist-open-data.s3.amazonaws.com/photos/{photo_id}/medium.jpeg"


def get_flag_severity(row: Dict[str, Any]) -> str:
    """
    Determine HOW WRONG the AI was biologically.

    near_miss        = same genus, wrong species
    moderate         = same family but wrong genus
    distant          = completely wrong organism
    detection_failure = no shared taxonomy at all
    """
    user_genus = (row.get("user_genus") or "").strip()
    ai_genus = (row.get("genus") or "").strip()
    user_family = (row.get("user_family") or "").strip()
    ai_family = (row.get("family") or "").strip()
    user_phylum = (row.get("user_phylum") or "").strip()
    ai_phylum = (row.get("phylum") or "").strip()
    user_kingdom = (row.get("user_kingdom") or "").strip()
    ai_kingdom = (row.get("kingdom") or "").strip()

    if user_genus and ai_genus and user_genus == ai_genus:
        return "near_miss"
    if user_family and ai_family and user_family == ai_family:
        return "moderate"
    if user_phylum and ai_phylum and user_phylum != ai_phylum:
        return "distant"
    if user_kingdom and ai_kingdom and user_kingdom != ai_kingdom:
        return "distant"

    return "moderate"


def get_flag_reason(row: Dict[str, Any]) -> str:
    """
    Generate human readable explanation of why this record was flagged.
    Derived from taxonomy columns since no manual notes available.
    """
    user_genus = (row.get("user_genus") or "").strip()
    ai_genus = (row.get("genus") or "").strip()
    user_family = (row.get("user_family") or "").strip()
    ai_family = (row.get("family") or "").strip()
    user_phylum = (row.get("user_phylum") or "").strip()
    ai_phylum = (row.get("phylum") or "").strip()
    score = float(row.get("score", 0) or 0)

    if user_genus and ai_genus and user_genus == ai_genus:
        return "Same genus, wrong species"
    if user_family and ai_family and user_family == ai_family:
        return "Same family, wrong genus"
    if user_phylum and ai_phylum and user_phylum != ai_phylum:
        return "Taxonomically distant misidentification"
    if score < 0.3:
        return "Very low confidence misidentification"

    return "Species mismatch"


def get_best_predictions(results_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    From 373k rows find the single best AI prediction per image.

    Step 1: Keep only top_no = 1 rows (best prediction per box)
    Step 2: Keep the box with the highest confidence score per image
    Result: 1 row per image = AI's single best answer
    """
    # Step 1 - keep only top ranked prediction per box
    top1_rows = [
        r for r in results_rows
        if str(r.get("top_no", "")).strip() == "1"
    ]

    # Step 2 - keep highest scoring box per image_id
    best: Dict[str, Dict[str, Any]] = {}
    for row in top1_rows:
        image_id = (row.get("image_id") or "").strip()
        if not image_id:
            continue
        score = float(row.get("score", 0) or 0)
        if image_id not in best or score > float(best[image_id].get("score", 0)):
            best[image_id] = row

    return best


def build_records(best_predictions: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build flagged records from full dataset.

    For each unique image:
    1. Check if Falsely identified = No Match
       (matches pipeline accuracy metric of 71.93%)
    2. Construct photo URL from photo_id
    3. Build complete record for database insertion
    """
    records = []

    for image_id, row in best_predictions.items():

        # FLAGGING RULE: use pipeline's own evaluation metric
        # Falsely identified = No Match means the pipeline
        # considered this a failure (accounts for genus-level
        # tolerance and taxonomic synonyms unlike same_species?)
        falsely_identified = str(
            row.get("Falsely identified", "")
        ).strip()

        if falsely_identified != "No Match":
            continue

        score = float(row.get("score", 0) or 0)

        # Extract photo_id and observation_id from image_id
        photo_id = extract_photo_id(image_id)
        observation_id = extract_observation_id(image_id)

        if not photo_id:
            continue

        # Construct iNaturalist S3 URL
        photo_url = construct_photo_url(photo_id)

        # Parse top-5 predictions JSON
        topk_json = "[]"
        top2_score = None
        confidence_gap = None

        topk_raw = row.get("topk_predictions_json") or "[]"
        try:
            topk_raw_clean = topk_raw.replace(": NaN", ": null")
            topk = json.loads(topk_raw_clean)
            topk_json = json.dumps(topk)

            # Confidence gap between top-1 and top-2
            # Small gap = model was uncertain between two options
            if len(topk) > 1:
                top2_score = float(topk[1].get("score") or 0)
                confidence_gap = round(score - top2_score, 4)

        except (json.JSONDecodeError, TypeError):
            topk_json = "[]"

        records.append({
            "image_id": image_id,
            "observation_id": observation_id,
            "photo_url": photo_url,
            "user_species": (row.get("User_classified") or "").strip(),
            "user_common_name": "",
            "ai_top1_species": (row.get("species") or "").strip(),
            "ai_top1_score": score,
            "ai_top2_score": top2_score,
            "confidence_gap": confidence_gap,
            "same_species": False,
            "topk_predictions": topk_json,
            "flag_reason": get_flag_reason(row),
            "flag_severity": get_flag_severity(row),
            "pred_prey": "",
            "validation_status": "pending",
        })

    return records


def load_records(
    cur: psycopg.Cursor,
    records: List[Dict[str, Any]]
) -> None:
    """
    Bulk insert flagged records into PostgreSQL.
    ON CONFLICT DO NOTHING prevents duplicates on re-run.
    """
    cur.executemany(
        """
        INSERT INTO validation_queue (
            image_id,
            observation_id,
            photo_url,
            user_species,
            user_common_name,
            ai_top1_species,
            ai_top1_score,
            ai_top2_score,
            confidence_gap,
            same_species,
            topk_predictions,
            flag_reason,
            flag_severity,
            pred_prey,
            validation_status
        ) VALUES (
            %(image_id)s,
            %(observation_id)s,
            %(photo_url)s,
            %(user_species)s,
            %(user_common_name)s,
            %(ai_top1_species)s,
            %(ai_top1_score)s,
            %(ai_top2_score)s,
            %(confidence_gap)s,
            %(same_species)s,
            %(topk_predictions)s,
            %(flag_reason)s,
            %(flag_severity)s,
            %(pred_prey)s,
            %(validation_status)s
        )
        ON CONFLICT (image_id) DO NOTHING
        """,
        records,
    )


def main() -> None:
    args = parse_args()

    # Step 1 - read results_crop.csv
    print(f"Reading results_crop from {args.results}...")
    results = read_csv(args.results)
    print(f"Read {len(results)} AI prediction rows.")

    # Step 2 - reduce 373k rows to 1 best prediction per image
    print("Finding best prediction per image...")
    best_predictions = get_best_predictions(results)
    print(f"Found best predictions for {len(best_predictions)} unique images.")

    # Step 3 - filter to flagged records only
    print("Building flagged records...")
    records = build_records(best_predictions)
    flagged_count = len(records)
    passing_count = len(best_predictions) - flagged_count
    print(f"Flagged (Falsely identified = No Match): {flagged_count}")
    print(f"Passing (Falsely identified = Match): {passing_count}")
    print(f"Percentage flagged: {flagged_count/len(best_predictions)*100:.1f}%")

    # Step 4 - load into PostgreSQL
    print("\nLoading into PostgreSQL...")
    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            load_records(cur, records)
        conn.commit()

    print(f"\nDone. Loaded {flagged_count} flagged records into validation_queue.")


if __name__ == "__main__":
    main()