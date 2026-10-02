"""
Image uploader script that downloads photos from iNaturalist S3
and uploads them to Cloudinary for fast CDN retrieval.

What this script does:
1. Reads validation_queue from PostgreSQL to get flagged image_ids
2. Constructs iNaturalist S3 URL from photo_id
3. Uploads to Cloudinary
4. Stores Cloudinary URL in images table
5. Updates validation_queue with image_record_id

NOTE: Do not run this script until licensing approval is confirmed
for storing iNaturalist photos on Cloudinary from the professor.

iNaturalist images have specific license codes per observation.
Check the license_code field in the observations data before
uploading any images to third party storage.

Usage (after approval):
  python3 -m backend.etl.image_uploader \
    --dsn postgresql://whodba:whopass@localhost:5433/who_eats_whom \
    --limit 100

Environment variables required:
  CLOUDINARY_CLOUD_NAME
  CLOUDINARY_API_KEY
  CLOUDINARY_API_SECRET
"""

from __future__ import annotations

import argparse
import os
import time
from typing import Any, Dict, List, Optional

import cloudinary
import cloudinary.uploader
import psycopg
from psycopg.rows import dict_row

# Configure Cloudinary from environment variables
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# ============================================================
# Licensing Notes
# ============================================================
# iNaturalist observations have the following license codes:
# cc0          - Public domain, no restrictions
# cc-by        - Attribution required
# cc-by-nc     - Attribution + non-commercial only
# cc-by-sa     - Attribution + share alike
# cc-by-nd     - Attribution + no derivatives
# cc-by-nc-sa  - Attribution + non-commercial + share alike
# cc-by-nc-nd  - Attribution + non-commercial + no derivatives
#
# For storing on Cloudinary:
# - cc0 and cc-by are safe to store
# - cc-by-nc requires confirming non-commercial use
# - All others require legal review before storage
#
# The validation platform is research/non-commercial so
# cc-by-nc should be acceptable but confirm with legal/prof.
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload iNaturalist images to Cloudinary."
    )
    parser.add_argument(
        "--dsn", required=True,
        help="Postgres connection string."
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max number of images to upload in one run (default 100)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be uploaded without actually uploading."
    )
    return parser.parse_args()


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


def construct_photo_url(photo_id: str, extension: str = "jpeg") -> str:
    """Construct iNaturalist S3 URL from photo_id."""
    return (
        f"https://inaturalist-open-data.s3.amazonaws.com"
        f"/photos/{photo_id}/medium.{extension}"
    )


def upload_to_cloudinary(
    photo_id: str
) -> Optional[Dict[str, Any]]:
    """
    Upload image from iNaturalist URL to Cloudinary.
    Tries jpeg first, falls back to jpg then png if it fails.
    """
    for extension in ["jpeg", "jpg", "png"]:
        url = construct_photo_url(photo_id, extension)
        try:
            result = cloudinary.uploader.upload(
                url,
                # Organize all images in one folder
                folder="who-eats-whom",
                # Use photo_id as public_id for easy reference
                public_id=f"photo_{photo_id}",
                # Don't overwrite if already uploaded
                overwrite=False,
                # Generate thumbnail for list views
                eager=[
                    {"width": 300, "height": 300, "crop": "fill"}
                ],
                # Tags for organization in Cloudinary dashboard
                tags=["who-eats-whom", "inaturalist"]
            )
            return result
        except Exception as e:
            error_msg = str(e).lower()
            # If format error try next extension
            if any(x in error_msg for x in ["invalid", "not found", "404", "error"]):
                continue
            # Real error - stop trying
            print(f"    Upload error for photo_{photo_id}: {e}")
            return None

    print(f"    All formats failed for photo_{photo_id}")
    return None


def insert_image_record(
    cur: psycopg.Cursor,
    photo_id: str,
    observation_id: str,
    inaturalist_url: str,
    cloudinary_result: Optional[Dict[str, Any]]
) -> Optional[int]:
    """
    Insert image record into images table.
    Returns the new image record id.
    """
    if cloudinary_result:
        cloudinary_public_id = cloudinary_result.get("public_id")
        cloudinary_url = cloudinary_result.get("secure_url")
        eager = cloudinary_result.get("eager", [])
        thumbnail_url = eager[0].get("secure_url") if eager else None
        image_format = cloudinary_result.get("format")
        upload_status = "uploaded"
    else:
        cloudinary_public_id = None
        cloudinary_url = None
        thumbnail_url = None
        image_format = None
        upload_status = "failed"

    cur.execute(
        """
        INSERT INTO images (
            photo_id,
            observation_id,
            inaturalist_url,
            cloudinary_public_id,
            cloudinary_url,
            cloudinary_thumbnail_url,
            image_format,
            upload_status,
            uploaded_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            CASE WHEN %s = 'uploaded' THEN NOW() ELSE NULL END
        )
        ON CONFLICT (photo_id) DO UPDATE SET
            cloudinary_public_id = EXCLUDED.cloudinary_public_id,
            cloudinary_url = EXCLUDED.cloudinary_url,
            cloudinary_thumbnail_url = EXCLUDED.cloudinary_thumbnail_url,
            image_format = EXCLUDED.image_format,
            upload_status = EXCLUDED.upload_status,
            uploaded_at = EXCLUDED.uploaded_at
        RETURNING id
        """,
        (
            photo_id,
            observation_id,
            inaturalist_url,
            cloudinary_public_id,
            cloudinary_url,
            thumbnail_url,
            image_format,
            upload_status,
            upload_status,
        )
    )
    row = cur.fetchone()
    return row[0] if row else None


def update_queue_image_record(
    cur: psycopg.Cursor,
    queue_id: int,
    image_record_id: int,
    cloudinary_url: Optional[str]
) -> None:
    """
    Link validation_queue record to its image record.
    Updates photo_url to Cloudinary URL for fast retrieval.
    """
    cur.execute(
        """
        UPDATE validation_queue
        SET
            image_record_id = %s,
            photo_url = COALESCE(%s, photo_url),
            updated_at = NOW()
        WHERE id = %s
        """,
        (image_record_id, cloudinary_url, queue_id)
    )


def get_pending_images(
    cur: psycopg.Cursor,
    limit: int
) -> List[Dict[str, Any]]:
    """
    Get records from validation_queue that don't have
    a Cloudinary image yet.
    Orders by id so we can resume where we left off.
    """
    cur.execute(
        """
        SELECT
            vq.id,
            vq.image_id,
            vq.observation_id,
            vq.photo_url
        FROM validation_queue vq
        WHERE vq.image_record_id IS NULL
        ORDER BY vq.id
        LIMIT %s
        """,
        (limit,)
    )
    return cur.fetchall()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        print("DRY RUN MODE - no images will be uploaded")

    print(f"Fetching up to {args.limit} images to upload...")

    uploaded = 0
    failed = 0
    skipped = 0

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            # Get pending records
            pending = get_pending_images(cur, args.limit)
            print(f"Found {len(pending)} images pending upload.\n")

            if not pending:
                print("All images already uploaded.")
                return

            for i, record in enumerate(pending):
                image_id = record["image_id"]
                queue_id = record["id"]
                observation_id = record.get("observation_id") or ""

                # Extract photo_id from image_id
                photo_id = extract_photo_id(image_id)
                if not photo_id:
                    print(
                        f"  [{i+1}/{len(pending)}] "
                        f"Could not extract photo_id from {image_id} - skipping"
                    )
                    skipped += 1
                    continue

                inaturalist_url = construct_photo_url(photo_id)
                print(f"  [{i+1}/{len(pending)}] photo_{photo_id}...")

                if args.dry_run:
                    print(f"    Would upload: {inaturalist_url}")
                    continue

                # Upload to Cloudinary
                result = upload_to_cloudinary(photo_id)

                # Insert into images table
                image_record_id = insert_image_record(
                    cur,
                    photo_id,
                    observation_id,
                    inaturalist_url,
                    result
                )

                # Update validation_queue with image_record_id
                cloudinary_url = result.get("secure_url") if result else None
                if image_record_id:
                    update_queue_image_record(
                        cur,
                        queue_id,
                        image_record_id,
                        cloudinary_url
                    )

                if result:
                    uploaded += 1
                    print(f"    ✓ {cloudinary_url}")
                else:
                    failed += 1
                    print(f"    ✗ Failed - will retry on next run")