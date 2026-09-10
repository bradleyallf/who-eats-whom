import requests

import psycopg
from postgres_loader_api_v2 import load_records_to_postgres

import os

DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://whodba:whopass@localhost:5433/who_eats_whom"
)


INATURALIST_TAXA_URL = "https://api.inaturalist.org/v1/taxa/{}"

def fetch_taxon_metadata(taxon_id):
    """Fetch Wikipedia, image, and licensing metadata for a taxon."""

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

    image_url = (
        default_photo.get("medium_url")
        or default_photo.get("small_url")
        or default_photo.get("square_url")
        or default_photo.get("url")
    )

    license_code = default_photo.get("license_code")
    attribution = default_photo.get("attribution")

    return (
        wikipedia_summary,
        wikipedia_url,
        image_url,
        license_code,
        attribution,
    )

def get_ofv(obs, field_name):
    target = field_name.strip().lower()
    for ofv in obs.get("ofvs", []):
        candidate = (ofv.get("name") or "").strip().lower()
        if candidate == target:
            return ofv.get("value")
    return None


def normalize(obs):
    taxon = obs.get("taxon") or {}
    user = obs.get("user") or {}
    geojson = obs.get("geojson") or {}
    coords = geojson.get("coordinates", [None, None])
    place = obs.get("place_guess")

    (
        wikipedia_summary,
        wikipedia_url,
        species_image_url,
        license_code,
        attribution,
    ) = fetch_taxon_metadata(taxon.get("id"))

    # photo = {}
    # if obs.get("photos"):
    #     photo = obs["photos"][0]

    return {
        # ------------------------
        # Observation
        # ------------------------
        "id": obs.get("id"),
        "uuid": obs.get("uuid"),
        "observed_on_string": obs.get("observed_on_string"),
        "observed_on": obs.get("observed_on"),
        "time_observed_at": obs.get("time_observed_at"),
        "time_zone": obs.get("time_zone"),

        # ------------------------
        # User
        # ------------------------
        "user_id": user.get("id"),
        "user_login": user.get("login"),
        "user_name": user.get("name"),

        # ------------------------
        # Metadata
        # ------------------------
        "created_at": obs.get("created_at"),
        "updated_at": obs.get("updated_at"),
        "quality_grade": obs.get("quality_grade"),
        "license": obs.get("license_code"),

        "url": f"https://www.inaturalist.org/observations/{obs.get('id')}",

        "wikipedia_summary": wikipedia_summary,
        "wikipedia_url": wikipedia_url,
        "image_url": species_image_url,
        "license_code": license_code,
        "attribution": attribution,
        "sound_url": None,
        "tag_list": ",".join(obs.get("tags", [])),
        "description": obs.get("description"),

        "num_identification_agreements": obs.get("identifications_count"),
        "num_identification_disagreements": obs.get("identification_disagreements_count"),

        "captive_cultivated": obs.get("captive"),
        "oauth_application_id": None,

        # ------------------------
        # Location
        # ------------------------
        "place_guess": place,
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

        # ------------------------
        # Place hierarchy
        # ------------------------
        "place_town_name": None,
        "place_county_name": None,
        "place_state_name": None,
        "place_country_name": None,
        "place_admin1_name": None,
        "place_admin2_name": None,

        # ------------------------
        # Taxon
        # ------------------------
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

        # ------------------------
        # Who Eats Whom fields
        # ------------------------
        'field:id meant for "eater" or organism being eaten?':
            get_ofv(obs, 'ID meant for "eater" or organism being eaten?'),

        'field:url for "partner" observation':
            get_ofv(obs, 'URL for "partner" observation'),

        "field:is observation one of these special types of feeding?":
            get_ofv(obs, "Is observation one of these special types of feeding?"),

        # ------------------------
        # Remaining export columns
        # ------------------------
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
        "identification_disagreements_count": obs.get("identification_disagreements_count"),
        "comments": None,
        "map_scale": None,
        "uri": f"https://www.inaturalist.org/observations/{obs.get('id')}",
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
    }

def fetch_and_update_observations():

    print("Checking existing observations in PostgreSQL...")

    existing_ids = set()

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
         cur.execute("SELECT observation_id FROM observations")
         existing_ids = {str(row[0]) for row in cur.fetchall()}

    params = {
        "project_id": "who-eats-whom",
        "quality_grade": "research",
        "created_d1": "2026-06-12",
        "created_d2": "2026-06-12",
        "per_page": 200
    }

    response = requests.get(
        "https://api.inaturalist.org/v1/observations",
        params=params
    )
    response.raise_for_status()
    data = response.json()

    new_records = []

    for obs in data["results"]:
        if str(obs["id"]) not in existing_ids:
            new_records.append(obs)

    print("New observations:", len(new_records))

    if not new_records:
        return []

    normalized_records = [normalize(o) for o in new_records]

    print(f"Fetched {len(normalized_records)} new observations")

    return normalized_records

# if __name__ == "__main__":
#     records = fetch_and_update_observations()

#     for record in records:
#         print("\n--- NEW RECORD ---")
#         print("id:", record["id"])
#         print("scientific_name:", record["scientific_name"])
#         print("taxon_id:", record["taxon_id"])
#         print("wikipedia_summary:", record["wikipedia_summary"])
#         print("wikipedia_url:", record["wikipedia_url"])
#         print("image_url:", record["image_url"])

if __name__ == "__main__":
    records = fetch_and_update_observations()

    if records:
        load_records_to_postgres(
            records,
            etl_version="2026-08-26-api",
            notes="Incremental observations fetched from iNaturalist API",
        )


