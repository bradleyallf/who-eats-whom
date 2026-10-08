"""Incremental iNaturalist importer for the Who Eats Whom project.
 
This module pulls observations from the "who-eats-whom" iNaturalist project,
skips the ones that already exist in PostgreSQL, enriches the new ones with
species-level metadata (Wikipedia summary, species photo), normalizes them
into the flat record shape expected by the database loader, and hands them off
to ``load_records_to_postgres``.
 
Pipeline overview:
    update_database()
        -> fetch_and_update_observations()   # query API, filter out known IDs
            -> normalize()                   # one record per new observation
                -> fetch_taxon_metadata()    # extra API call per observation
                -> find_allowed_photo()      # pick a license-compatible photo
                -> get_ofv()                 # read custom observation fields
        -> load_records_to_postgres()        # write to PostgreSQL
 
Environment variables:
    POSTGRES_DSN: PostgreSQL connection string. Defaults to the local Docker
        Compose database (port 5433).
"""

import requests
import os
from datetime import datetime, timezone

import psycopg
from postgres_loader_api_v3 import load_records_to_postgres

# PostgreSQL connection string. Override with the POSTGRES_DSN environment
# variable; the default matches the postgres service in docker-compose.yml.
DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://whodba:whopass@localhost:5433/who_eats_whom"
)

# iNaturalist API endpoint for a single taxon. Use .format(taxon_id).
INATURALIST_TAXA_URL = (
    "https://api.inaturalist.org/v1/taxa/{}"
)

# iNaturalist API endpoint for searching observations.
INATURALIST_OBSERVATIONS_URL = (
    "https://api.inaturalist.org/v1/observations"
)


# These are the licenses allowed for observation images.
ALLOWED_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
    "pd",
    "gfdl",
}


def fetch_taxon_metadata(taxon_id):
    """Fetch Wikipedia and species-image metadata for a taxon."""

    if not taxon_id:
        return None, None, None, None, None

    url = INATURALIST_TAXA_URL.format(taxon_id)

    response = requests.get(
        url,
        headers={"User-Agent": "Who-Eats-Whom/1.0"},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        print(f"No taxon data found for taxon_id={taxon_id}")
        return None, None, None, None, None

    taxon = results[0]

    wikipedia_summary = taxon.get("wikipedia_summary")
    wikipedia_url = taxon.get("wikipedia_url")

    default_photo = taxon.get("default_photo") or {}

    species_image_url = (
        default_photo.get("medium_url")
        or default_photo.get("small_url")
        or default_photo.get("square_url")
        or default_photo.get("url")
    )

    # Licensing/credit info for the species photo, needed for display. 
    species_license_code = default_photo.get("license_code")
    species_attribution = default_photo.get("attribution")

    return (
        wikipedia_summary,
        wikipedia_url,
        species_image_url,
        species_license_code,
        species_attribution,
    )


def find_allowed_photo(photos):
    """Return the first photo with an allowed license.
 
    Args:
        photos: List of photo dicts from an iNaturalist observation (may be
            None or empty).
 
    Returns:
        The first photo dict whose ``license_code`` is in
        ``ALLOWED_LICENSES``, or None if there is no such photo.
    """

    for photo in photos or []:
        license_code = (
            photo.get("license_code") or ""
        ).lower()

        if license_code in ALLOWED_LICENSES:
            return photo

    return None


def get_ofv(obs, field_name):
    """Return the first photo with an allowed license.
 
    Args:
        photos: List of photo dicts from an iNaturalist observation (may be
            None or empty).
 
    Returns:
        The first photo dict whose ``license_code`` is in
        ``ALLOWED_LICENSES``, or None if there is no such photo.
    """

    target = field_name.strip().lower()

    for ofv in obs.get("ofvs", []):
        candidate = (ofv.get("name") or "").strip().lower()

        if candidate == target:
            return ofv.get("value")

    return None


def normalize(obs, pull_id):
    """Convert a raw iNaturalist observation into a flat database record.
 
    The returned dict has one key per column expected by
    ``load_records_to_postgres``. Columns this script cannot fill from the
    API response are set to None so the loader always receives a full set of
    keys.
 
    Side effect: calls ``fetch_taxon_metadata``, which makes one network
    request per observation.
 
    Args:
        obs: Observation dict from the iNaturalist API.
        pull_id: Identifier for this import run (e.g.
            ``scheduler_20261007_190419``), stored in ``inat_api_call`` so
            rows can be traced back to the run that created them.
 
    Returns:
        A flat dict of column name -> value.
    """

    taxon = obs.get("taxon") or {}
    user = obs.get("user") or {}
    geojson = obs.get("geojson") or {}
    coords = geojson.get("coordinates", [None, None])
    place = obs.get("place_guess")

    # ---------------------------------------
    # Species-level image metadata
    # ---------------------------------------
    (
        wikipedia_summary,
        wikipedia_url,
        species_image_url,
        species_license_code,
        species_attribution,
    ) = fetch_taxon_metadata(taxon.get("id"))

    # ---------------------------------------
    # Observation-level image metadata
    # ---------------------------------------
    photo = find_allowed_photo(
        obs.get("photos", [])
    )

    if photo is None:
        observation_image_url = None
        photo_license_code = None
        photo_attribution = None

        print(
            f"Observation {obs.get('id')}: "
            f"no allowed licensed photo found"
        )

    else:
        observation_image_url = photo.get("url")

        photo_license_code = (
            photo.get("license_code") or None
        )

        if photo_license_code:
            photo_license_code = photo_license_code.lower()

        photo_attribution = photo.get("attribution")

    # Single timestamp (UTC) recording when this record was fetched.
    pulled_at = datetime.now(timezone.utc)

    return {
        # ---------------------------------------
        # Observation
        # ---------------------------------------
        "id": obs.get("id"),
        "uuid": obs.get("uuid"),
        "observed_on_string": obs.get("observed_on_string"),
        "observed_on": obs.get("observed_on"),
        "time_observed_at": obs.get("time_observed_at"),
        "time_zone": obs.get("time_zone"),

        # ---------------------------------------
        # User
        # ---------------------------------------
        "user_id": user.get("id"),
        "user_login": user.get("login"),
        "user_name": user.get("name"),

        # ---------------------------------------
        # Metadata
        # ---------------------------------------
        "created_at": obs.get("created_at"),
        "updated_at": obs.get("updated_at"),
        "quality_grade": obs.get("quality_grade"),

        "url": (
            f"https://www.inaturalist.org/observations/"
            f"{obs.get('id')}"
        ),

        "wikipedia_summary": wikipedia_summary,
        "wikipedia_url": wikipedia_url,

        # Species image
        "image_url": species_image_url,
        "species_license_code": species_license_code,
        "species_attribution": species_attribution,

        # Observation image
        "photo_license_code": photo_license_code,
        "photo_attribution": photo_attribution,
        "observation_image_url": observation_image_url,

        "sound_url": None,
        "tag_list": ",".join(obs.get("tags", [])),
        "description": obs.get("description"),

        "num_identification_agreements":
            obs.get("identifications_count"),

        "num_identification_disagreements":
            obs.get("identification_disagreements_count"),

        "captive_cultivated": obs.get("captive"),
        "oauth_application_id": None,

        # ---------------------------------------
        # Location
        # ---------------------------------------
        "place_guess": place,

        "latitude":
            coords[1] if len(coords) == 2 else None,

        "longitude":
            coords[0] if len(coords) == 2 else None,

        "positional_accuracy":
            obs.get("public_positional_accuracy"),

        "private_place_guess": None,
        "private_latitude": None,
        "private_longitude": None,

        "public_positional_accuracy":
            obs.get("public_positional_accuracy"),

        "geoprivacy": obs.get("geoprivacy"),
        "taxon_geoprivacy": obs.get("taxon_geoprivacy"),
        "coordinates_obscured": obs.get("obscured"),

        "positioning_method": None,
        "positioning_device": None,

        # ---------------------------------------
        # Taxon
        # ---------------------------------------
        "species_guess": obs.get("species_guess"),
        "scientific_name": taxon.get("name"),
        "common_name": taxon.get("preferred_common_name"),
        "iconic_taxon_name": taxon.get("iconic_taxon_name"),

        "taxon_id": taxon.get("id"),

        "taxon_kingdom_name": None,
        "taxon_phylum_name": None,
        "taxon_subphylum_name": None,
        "taxon_superclass_name": None,
        "taxon_class_name": None,
        "taxon_subclass_name": None,
        "taxon_superorder_name": None,
        "taxon_order_name": None,
        "taxon_suborder_name": None,
        "taxon_superfamily_name": None,
        "taxon_family_name": None,
        "taxon_subfamily_name": None,
        "taxon_supertribe_name": None,
        "taxon_tribe_name": None,
        "taxon_subtribe_name": None,
        "taxon_genus_name": None,
        "taxon_genushybrid_name": None,
        "taxon_species_name": None,
        "taxon_hybrid_name": None,
        "taxon_subspecies_name": None,
        "taxon_variety_name": None,
        "taxon_form_name": None,

        # ---------------------------------------
        # Who Eats Whom fields
        # ---------------------------------------
        'field:id meant for "eater" or organism being eaten?':
            get_ofv(
                obs,
                'ID meant for "eater" or organism being eaten?'
            ),

        'field:url for "partner" observation':
            get_ofv(
                obs,
                'URL for "partner" observation'
            ),

        "field:is observation one of these special types of feeding?":
            get_ofv(
                obs,
                "Is observation one of these special types of feeding?"
            ),

        # ---------------------------------------
        # Existing fields
        # ---------------------------------------
        "annotations": None,
        "observed_on_details": None,
        "cached_votes_total": None,
        "identifications_most_agree": None,
        "created_at_details": None,
        "identifications_most_disagree": None,
        "tags": None,
        "comments_count": obs.get("comments_count"),
        "site_id": obs.get("site_id"),
        "created_time_zone": None,

        # This is the observation's original
        # iNaturalist license, not the selected
        # photo license.
        "license_code": obs.get("license_code"),

        "observed_time_zone": None,
        "quality_metrics": None,
        "reviewed_by": None,
        "flags": None,
        "time_zone_offset": None,
        "project_ids_with_curator_id": None,
        "sounds": None,
        "place_ids": None,
        "captive": obs.get("captive"),
        "taxon": None,
        "ident_taxon_ids": None,
        "outlinks": None,
        "faves_count": obs.get("faves_count"),
        "ofvs": None,
        "preferences": None,
        "identification_disagreements_count":
            obs.get("identification_disagreements_count"),

        "comments": None,
        "map_scale": None,

        "uri": (
            f"https://www.inaturalist.org/observations/"
            f"{obs.get('id')}"
        ),

        "project_ids": None,
        "community_taxon_id": obs.get("community_taxon_id"),
        "geojson": None,
        "owners_identification_from_vision": None,
        "identifications_count": obs.get("identifications_count"),
        "obscured": obs.get("obscured"),

        "location":
            f"{coords[1]},{coords[0]}"
            if len(coords) == 2
            else None,

        "votes": None,
        "spam": None,
        "user": None,
        "mappable": obs.get("mappable"),
        "identifications_some_agree": None,
        "project_ids_without_curator_id": None,
        "identifications": None,
        "project_observations": None,
        "observation_photos": None,
        "photos": None,
        "faves": None,
        "non_owner_ids": None,

        # ---------------------------------------
        # New scheduler tracking fields
        # ---------------------------------------
        "inat_pulled_at": pulled_at,
        "inat_api_call": pull_id,
    }

def fetch_and_update_observations():
    """Fetch new project observations from iNaturalist.
 
    Steps:
        1. Load all observation IDs already stored in PostgreSQL.
        2. Query iNaturalist for research-grade observations in the
           "who-eats-whom" project (see the date filter note below).
        3. Keep only observations whose ID is not already in the database.
        4. Normalize the new ones (which also fetches species metadata).
 
    Returns:
        A list of normalized record dicts ready for the loader. The list is
        empty when there is nothing new.
 
    Raises:
        requests.HTTPError: If the observations request fails.
        psycopg.Error: If the existing-IDs query fails.
    """

    print("Checking existing observations in PostgreSQL...")

    existing_ids = set()

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT observation_id FROM observations"
            )
            existing_ids = {
                str(row[0])
                for row in cur.fetchall()
            }

    params = {
        "project_id": "who-eats-whom",
        "quality_grade": "research",
        "created_d1": "2026-10-02",
        "created_d2": "2026-10-02",
        "per_page": 200,
    }

    response = requests.get(
        INATURALIST_OBSERVATIONS_URL,
        params=params,
        headers={"User-Agent": "Who-Eats-Whom/1.0"},
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    new_records = []

    # Keep only observations we have not stored yet.
    for obs in data["results"]:
        if str(obs["id"]) not in existing_ids:
            new_records.append(obs)

    print("New observations:", len(new_records))

    if not new_records:
        return []

    # One identifier for this scheduler/API pull.
    pull_id = (
        f"scheduler_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )

    normalized_records = [
        normalize(o, pull_id)
        for o in new_records
    ]

    print(
        f"Fetched {len(normalized_records)} new observations"
    )

    return normalized_records

def update_database():
    """Run one incremental import: fetch new observations and store them.
 
    Returns:
        The number of new observations that were fetched (and loaded).
    """
    records = fetch_and_update_observations()

    if records:
        load_records_to_postgres(
            records,
            etl_version="2026-08-26-api",
            notes="Incremental observations fetched from iNaturalist API",
        )

    return len(records)


if __name__ == "__main__":
    update_database()



