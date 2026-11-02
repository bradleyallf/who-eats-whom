"""Incremental iNaturalist importer for the Who Eats Whom project.

Pulls research-grade observations from the "who-eats-whom" iNaturalist project
that changed since the last successful run (stored in the ``scheduler_state``
table), enriches them, normalizes them and upserts them into PostgreSQL.

Enrichment:
    * Species metadata (Wikipedia summary, photo, rank, kingdom..genus) from
      /v1/taxa, fetched 30 taxa per request.
    * Place names (country/state/county/town) from /v1/places, resolved from
      each observation's ``place_ids``, fetched 100 places per request.

First run: ``last_fetched`` is the seed date (1645-08-26), so everything in the
project is imported. After each successful run ``last_fetched`` is set to the
time that run started, so the next run only picks up what changed since.

Pipeline overview:
    update_database()
        -> get_last_fetched()
        -> fetch_observation_pages()      # paginated API query
            -> prefetch_taxa()            # batch species lookups
            -> prefetch_places()          # batch place lookups
            -> normalize()                # one flat record per observation
        -> load_records_to_postgres()     # upsert one page at a time
        -> set_last_fetched()             # only after everything succeeded

Environment variables:
    POSTGRES_DSN: PostgreSQL connection string (default: local Docker DB).
"""

import time
from datetime import datetime, timezone

import requests

from postgres_loader_api_v2 import (
    get_last_fetched,
    load_records_to_postgres,
    set_last_fetched,
)

INATURALIST_TAXA_URL = "https://api.inaturalist.org/v1/taxa/{}"
INATURALIST_PLACES_URL = "https://api.inaturalist.org/v1/places/{}"
INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"

HEADERS = {"User-Agent": "Who-Eats-Whom/1.0"}
PER_PAGE = 200
PAUSE_SECONDS = 1.0  # be polite to the iNaturalist API (~60 requests/min limit)
TAXA_BATCH_SIZE = 30     # the taxa endpoint accepts up to 30 ids per request
PLACES_BATCH_SIZE = 100  # places endpoint accepts a comma-separated id list

# iNaturalist rejects/ignores absurdly old dates, so for the very first run we
# simply leave the filter off (which means "everything").
MIN_USEFUL_YEAR = 1900

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

# Ranks stored in the species table.
TAXONOMY_RANKS = ("kingdom", "phylum", "class", "order", "family", "genus")

# iNaturalist place admin levels -> the place field they fill.
PLACE_LEVELS = {0: "country", 10: "state", 20: "county", 30: "town"}

# Per-run caches.
TAXON_CACHE = {}  # taxon_id -> dict from parse_taxon()
PLACE_CACHE = {}  # place_id -> (admin_level, name)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def get_with_retry(url, params=None, timeout=30, max_retries=5):
    """GET with exponential backoff for network errors, 429s and 5xx responses."""
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=timeout
            )
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(
                    f"HTTP {response.status_code}", response=response
                )
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)

            # Real client errors (404, 400, ...) won't fix themselves.
            if status and 400 <= status < 500 and status != 429:
                raise

            if attempt == max_retries:
                raise

            wait = 2 ** attempt
            print(f"  Request failed ({exc.__class__.__name__}); "
                  f"retry {attempt}/{max_retries - 1} in {wait}s...")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Taxa (species metadata + taxonomy)
# ---------------------------------------------------------------------------

def parse_taxon(taxon):
    """Extract species metadata and taxonomy from an iNaturalist taxon record.

    Returns a dict with wikipedia_summary, wikipedia_url, image_url,
    license_code, attribution, rank and one key per rank in TAXONOMY_RANKS.
    """
    default_photo = taxon.get("default_photo") or {}

    image_url = (
        default_photo.get("medium_url")
        or default_photo.get("small_url")
        or default_photo.get("square_url")
        or default_photo.get("url")
    )

    info = {
        "wikipedia_summary": taxon.get("wikipedia_summary"),
        "wikipedia_url": taxon.get("wikipedia_url"),
        "image_url": image_url,
        "license_code": default_photo.get("license_code"),
        "attribution": default_photo.get("attribution"),
        "rank": taxon.get("rank"),
    }

    # Lineage: every ancestor, plus the taxon itself if it is at one of the
    # ranks we store (so e.g. an order-level taxon has order_name == its name).
    lineage = {}
    for ancestor in taxon.get("ancestors") or []:
        if ancestor.get("rank") in TAXONOMY_RANKS:
            lineage[ancestor["rank"]] = ancestor.get("name")
    if taxon.get("rank") in TAXONOMY_RANKS:
        lineage[taxon["rank"]] = taxon.get("name")

    for rank in TAXONOMY_RANKS:
        info[rank] = lineage.get(rank)

    return info


def prefetch_taxa(taxon_ids):
    """Fetch metadata for many taxa at once (30 per request) into TAXON_CACHE.

    Taxa already in the cache are skipped, so each taxon is requested at most
    once per run.
    """
    missing = sorted({t for t in taxon_ids if t and t not in TAXON_CACHE})

    for i in range(0, len(missing), TAXA_BATCH_SIZE):
        batch = missing[i : i + TAXA_BATCH_SIZE]
        ids_param = ",".join(str(t) for t in batch)

        response = get_with_retry(
            INATURALIST_TAXA_URL.format(ids_param),
            params={"per_page": TAXA_BATCH_SIZE},
        )

        for taxon in response.json().get("results", []):
            TAXON_CACHE[taxon["id"]] = parse_taxon(taxon)

        # Anything iNaturalist didn't return: remember it as empty so we
        # don't ask again.
        for t in batch:
            if t not in TAXON_CACHE:
                print(f"No taxon data found for taxon_id={t}")
                TAXON_CACHE[t] = {}

        time.sleep(PAUSE_SECONDS)


def fetch_taxon_metadata(taxon_id):
    """Return the cached taxon info dict (fetching it if needed)."""
    if not taxon_id:
        return {}

    if taxon_id not in TAXON_CACHE:
        prefetch_taxa([taxon_id])

    return TAXON_CACHE[taxon_id]


# ---------------------------------------------------------------------------
# Places (country / state / county / town names)
# ---------------------------------------------------------------------------

def prefetch_places(observations):
    """Fetch names for every place_id on the given observations (100 per request)."""
    ids = set()
    for obs in observations:
        ids.update(obs.get("place_ids") or [])

    missing = sorted(p for p in ids if p not in PLACE_CACHE)
    if missing:
        print(f"Fetching {len(missing)} places...")

    for i in range(0, len(missing), PLACES_BATCH_SIZE):
        batch = missing[i : i + PLACES_BATCH_SIZE]
        ids_param = ",".join(str(p) for p in batch)

        try:
            response = get_with_retry(INATURALIST_PLACES_URL.format(ids_param))
            results = response.json().get("results", [])
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                results = []
            else:
                raise

        for place in results:
            PLACE_CACHE[place["id"]] = (place.get("admin_level"), place.get("name"))

        # Places that weren't returned: remember them as unknown.
        unreturned = [p for p in batch if p not in PLACE_CACHE]
        if unreturned:
            print(f"  {len(unreturned)} places not returned by iNaturalist")
        for p in unreturned:
            PLACE_CACHE[p] = (None, None)

        time.sleep(PAUSE_SECONDS)


def get_place_names(obs):
    """Return {"country": ..., "state": ..., "county": ..., "town": ...} for an observation."""
    names = {}
    for place_id in obs.get("place_ids") or []:
        level, name = PLACE_CACHE.get(place_id, (None, None))
        label = PLACE_LEVELS.get(level)
        if label and label not in names:
            names[label] = name
    return names


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_allowed_photo(photos):
    """Return the first photo whose license_code is in ALLOWED_LICENSES, else None."""
    for photo in photos or []:
        license_code = (photo.get("license_code") or "").lower()
        if license_code in ALLOWED_LICENSES:
            return photo
    return None


def get_ofv(obs, field_name):
    """Return the value of the custom observation field ``field_name`` (or None).

    Matching is case/whitespace-insensitive on the field name.
    """
    target = field_name.strip().lower()

    for ofv in obs.get("ofvs") or []:
        candidate = (ofv.get("name") or "").strip().lower()
        if candidate == target:
            return ofv.get("value")

    return None


def normalize(obs, pull_id):
    """Convert a raw iNaturalist observation into a flat database record.

    Columns this script cannot fill from the API are set to None so the loader
    always receives a full set of keys. Uses the taxon and place caches (and
    fetches on a miss).

    Args:
        obs: Observation dict from the iNaturalist API.
        pull_id: Identifier for this import run (e.g. ``scheduler_20261026_190419``).
    """
    taxon = obs.get("taxon") or {}
    user = obs.get("user") or {}
    geojson = obs.get("geojson") or {}
    coords = geojson.get("coordinates") or [None, None]
    place = obs.get("place_guess")

    info = fetch_taxon_metadata(taxon.get("id"))
    place_names = get_place_names(obs)

    photo = find_allowed_photo(obs.get("photos", []))

    if photo is None:
        observation_image_url = None
        photo_license_code = None
        photo_attribution = None
        print(f"Observation {obs.get('id')}: no allowed licensed photo found")
    else:
        observation_image_url = photo.get("url")
        photo_license_code = (photo.get("license_code") or "").lower() or None
        photo_attribution = photo.get("attribution")

    pulled_at = datetime.now(timezone.utc)
    obs_url = f"https://www.inaturalist.org/observations/{obs.get('id')}"

    return {
        # Observation
        "id": obs.get("id"),
        "uuid": obs.get("uuid"),
        "observed_on_string": obs.get("observed_on_string"),
        "observed_on": obs.get("observed_on"),
        "time_observed_at": obs.get("time_observed_at"),
        "time_zone": obs.get("time_zone"),

        # User
        "user_id": user.get("id"),
        "user_login": user.get("login"),
        "user_name": user.get("name"),

        # Metadata
        "created_at": obs.get("created_at"),
        "updated_at": obs.get("updated_at"),
        "quality_grade": obs.get("quality_grade"),
        "url": obs_url,

        "wikipedia_summary": info.get("wikipedia_summary"),
        "wikipedia_url": info.get("wikipedia_url"),

        # Species image
        "image_url": info.get("image_url"),
        "species_license_code": info.get("license_code"),
        "species_attribution": info.get("attribution"),

        # Observation image
        "photo_license_code": photo_license_code,
        "photo_attribution": photo_attribution,
        "observation_image_url": observation_image_url,

        "sound_url": None,
        "tag_list": ",".join(obs.get("tags") or []),
        "description": obs.get("description"),
        "num_identification_agreements": obs.get("identifications_count"),
        "num_identification_disagreements": obs.get("identification_disagreements_count"),
        "captive_cultivated": obs.get("captive"),
        "oauth_application_id": None,

        # Location
        "place_guess": place,
        "place_country_name": place_names.get("country"),
        "place_state_name": place_names.get("state"),
        "place_county_name": place_names.get("county"),
        "place_town_name": place_names.get("town"),
        "latitude": coords[1] if len(coords) == 2 else None,
        "longitude": coords[0] if len(coords) == 2 else None,
        "positional_accuracy": obs.get("public_positional_accuracy"),
        "private_place_guess": None,
        "private_latitude": None,
        "private_longitude": None,
        "public_positional_accuracy": obs.get("public_positional_accuracy"),
        "geoprivacy": obs.get("geoprivacy"),
        "taxon_geoprivacy": obs.get("taxon_geoprivacy"),
        "coordinates_obscured": obs.get("obscured"),
        "positioning_method": None,
        "positioning_device": None,

        # Taxon
        "species_guess": obs.get("species_guess"),
        "scientific_name": taxon.get("name"),
        "common_name": taxon.get("preferred_common_name"),
        "iconic_taxon_name": taxon.get("iconic_taxon_name"),
        "taxon_id": taxon.get("id"),
        "taxon_rank": info.get("rank") or taxon.get("rank"),

        "taxon_kingdom_name": info.get("kingdom"),
        "taxon_phylum_name": info.get("phylum"),
        "taxon_subphylum_name": None,
        "taxon_superclass_name": None,
        "taxon_class_name": info.get("class"),
        "taxon_subclass_name": None,
        "taxon_superorder_name": None,
        "taxon_order_name": info.get("order"),
        "taxon_suborder_name": None,
        "taxon_superfamily_name": None,
        "taxon_family_name": info.get("family"),
        "taxon_subfamily_name": None,
        "taxon_supertribe_name": None,
        "taxon_tribe_name": None,
        "taxon_subtribe_name": None,
        "taxon_genus_name": info.get("genus"),
        "taxon_genushybrid_name": None,
        "taxon_species_name": None,
        "taxon_hybrid_name": None,
        "taxon_subspecies_name": None,
        "taxon_variety_name": None,
        "taxon_form_name": None,

        # Who Eats Whom fields
        'field:id meant for "eater" or organism being eaten?':
            get_ofv(obs, 'ID meant for "eater" or organism being eaten?'),
        'field:url for "partner" observation':
            get_ofv(obs, 'URL for "partner" observation'),
        "field:is observation one of these special types of feeding?":
            get_ofv(obs, "Is observation one of these special types of feeding?"),

        # Existing fields
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

        # The observation's original iNaturalist license, not the photo license.
        "license_code": obs.get("license_code"),

        "observed_time_zone": None,
        "quality_metrics": None,
        "reviewed_by": None,
        "flags": None,
        "time_zone_offset": None,
        "project_ids_with_curator_id": None,
        "sounds": None,
        "place_ids": obs.get("place_ids"),
        "captive": obs.get("captive"),
        "taxon": None,
        "ident_taxon_ids": None,
        "outlinks": None,
        "faves_count": obs.get("faves_count"),
        "ofvs": None,
        "preferences": None,
        "identification_disagreements_count": obs.get("identification_disagreements_count"),
        "comments": None,
        "map_scale": None,
        "uri": obs_url,
        "project_ids": None,
        "community_taxon_id": obs.get("community_taxon_id"),
        "geojson": None,
        "owners_identification_from_vision": None,
        "identifications_count": obs.get("identifications_count"),
        "obscured": obs.get("obscured"),
        "location": f"{coords[1]},{coords[0]}" if len(coords) == 2 else None,
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

        # Scheduler tracking fields
        "inat_pulled_at": pulled_at,
        "inat_api_call": pull_id,
    }


# ---------------------------------------------------------------------------
# Fetching and running
# ---------------------------------------------------------------------------

def fetch_observation_pages(since):
    """Yield lists of raw observations (one API page each) updated since ``since``.

    Pages by ascending observation id (``id_above``) instead of page numbers,
    because iNaturalist caps page-based paging at 10,000 results.
    """
    last_id = 0

    while True:
        params = {
            "project_id": "who-eats-whom",
            "quality_grade": "research",
            "order_by": "id",
            "order": "asc",
            "id_above": last_id,
            "per_page": PER_PAGE,
        }

        # Omit the filter for the seed date => fetch everything.
        if since.year >= MIN_USEFUL_YEAR:
            params["updated_since"] = since.isoformat()

        response = get_with_retry(
            INATURALIST_OBSERVATIONS_URL, params=params, timeout=60
        )

        results = response.json().get("results", [])
        if not results:
            return

        yield results

        last_id = max(o["id"] for o in results)

        if len(results) < PER_PAGE:
            return

        time.sleep(PAUSE_SECONDS)


def update_database():
    """Run one incremental import and advance ``last_fetched``.

    ``last_fetched`` is only advanced after every page loaded successfully, and
    it is set to the time this run STARTED, so nothing that changes while the
    run is in progress can be missed. If a run fails halfway, the next run
    starts from the old value; the upserts make re-processing harmless.

    Returns:
        Number of observations written to PostgreSQL.
    """
    run_started = datetime.now(timezone.utc)
    pull_id = f"scheduler_{run_started.strftime('%Y%m%d_%H%M%S')}"

    since = get_last_fetched()
    reason = "first scheduler run" if since.year < MIN_USEFUL_YEAR else "scheduler update"
    print(f"Fetching research-grade observations updated since {since.isoformat()}")

    total = 0

    for page in fetch_observation_pages(since):
        prefetch_taxa((obs.get("taxon") or {}).get("id") for obs in page)
        prefetch_places(page)
        records = [normalize(obs, pull_id) for obs in page]
        total += load_records_to_postgres(records, updated_due_to=reason)
        print(f"Loaded so far: {total}")

    set_last_fetched(run_started)
    print(f"Done. {total} observations written. last_fetched = {run_started.isoformat()}")

    return total


if __name__ == "__main__":
    update_database()