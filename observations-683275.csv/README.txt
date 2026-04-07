Exported at 2026-02-18T18:12:09Z

Query: quality_grade=any&identifications=any&projects%5B%5D=who-eats-whom

Columns:
id: Unique, sequential identifier for the observation
uuid: Universally unique identifier for the observation. See https://datatracker.ietf.org/doc/html/rfc9562
observed_on_string: Date/time as entered by the observer
observed_on: Normalized date of observation
time_observed_at: Normalized datetime of observation
time_zone: Time zone of observation
user_id: Unique, sequential identifier for the observer
user_login: Handle / username of the observer, i.e. a short, unique, alphanumeric identifier for a user
user_name: Name of the observer, generally used for attribution on the site. This is an optional field and may be a pseudonym
created_at: Datetime observation was created
updated_at: Datetime observation was last updated
quality_grade: Quality grade of this observation. See Help section for details on what this means. See https://help.inaturalist.org/support/solutions/articles/151000169936
license: Identifier for the license or waiver the observer has chosen for this observation. All rights reserved if blank
url: URL for the observation
image_url: URL for the first photo associated with the observation
sound_url: URL for the first sound associated with the observation. Note this will only be present for direct uploads, not sounds hosted on 3rd-party services
tag_list: Comma-separated list of tags
description: Text written by the observer describing the observation or recording any other notes that seem relevant
num_identification_agreements: Number of identifications associated with taxa that match or are contained by the taxon from the observer's identification
num_identification_disagreements: Number of identifications associated with taxa that do not match and are not contained by the taxon from the observer's identification
captive_cultivated: Observation is of an organism that exists in the time and place it was observed because humans intended it to be then and there. For more, see https://help.inaturalist.org/support/solutions/articles/151000169932
oauth_application_id: Sequential identifier for the application that created the observation. For more information about the application, append this number to https://www.inaturalist.org/oauth/applications/
place_guess: Locality description as entered by the observer
latitude: Publicly visible latitude from the observation location
longitude: Publicly visible longitude from the observation location
positional_accuracy: Coordinate precision (yeah, yeah, accuracy != precision, poor choice of names)
private_place_guess: Observation location as written by the observer if location obscured
private_latitude: Private latitude, set if observation private or obscured
private_longitude: Private longitude, set if observation private or obscured
public_positional_accuracy: Maximum horizontal positional uncertainty in meters; includes uncertainty added by coordinate obscuration
geoprivacy: Whether or not the observer has chosen to obscure or hide the coordinates. See https://help.inaturalist.org/support/solutions/articles/151000169938
taxon_geoprivacy: Most conservative geoprivacy applied due to the conservation statuses of taxa in current identification.
coordinates_obscured: Whether or not the coordinates have been obscured, either because of geoprivacy or because of a threatened taxon
positioning_method: How the coordinates were determined
positioning_device: Device used to determine coordinates
place_town_name: The name of the town or city that contains this observation's coordinates, if known
place_county_name: The name of the third-level administrative area that contains this observation's coordinates (e.g. a county in most parts of the United States)
place_state_name: The name of the second-level administrative area that contains this observation's coordinates (e.g. a state in most parts of the United States)
place_country_name: The name of the country that contains this observation's coordinates
place_admin1_name: Name of the administrative place one rank below the country level
place_admin2_name: Name of the administrative place two ranks below the country level
species_guess: Plain text name of the observed taxon; can be set by the observer during observation creation, but can get replaced with canonical, localized names when the taxon changes
scientific_name: Scientific name of the observed taxon according to iNaturalist
common_name: Common or vernacular name of the observed taxon according to iNaturalist
iconic_taxon_name: Higher-level taxonomic category for the observed taxon
taxon_id: Unique, sequential identifier for the observed taxon
taxon_kingdom_name: Name of the taxonomic kingdom containing the observed taxon
taxon_phylum_name: Name of the taxonomic phylum containing the observed taxon
taxon_subphylum_name: Name of the taxonomic subphylum containing the observed taxon
taxon_superclass_name: Name of the taxonomic superclass containing the observed taxon
taxon_class_name: Name of the taxonomic class containing the observed taxon
taxon_subclass_name: Name of the taxonomic subclass containing the observed taxon
taxon_superorder_name: Name of the taxonomic superorder containing the observed taxon
taxon_order_name: Name of the taxonomic order containing the observed taxon
taxon_suborder_name: Name of the taxonomic suborder containing the observed taxon
taxon_superfamily_name: Name of the taxonomic superfamily containing the observed taxon
taxon_family_name: Name of the taxonomic family containing the observed taxon
taxon_subfamily_name: Name of the taxonomic subfamily containing the observed taxon
taxon_supertribe_name: Name of the taxonomic supertribe containing the observed taxon
taxon_tribe_name: Name of the taxonomic tribe containing the observed taxon
taxon_subtribe_name: Name of the taxonomic subtribe containing the observed taxon
taxon_genus_name: Name of the taxonomic genus containing the observed taxon
taxon_genushybrid_name: Name of the taxonomic hybrid genus containing the observed taxon
taxon_species_name: Name of the taxonomic species containing the observed taxon
taxon_hybrid_name: Name of the taxonomic hybrid containing the observed taxon
taxon_subspecies_name: Name of the taxonomic subspecies containing the observed taxon
taxon_variety_name: Name of the taxonomic variety containing the observed taxon
taxon_form_name: Name of the taxonomic form containing the observed taxon
field:id+meant+for+%22eater%22+or+organism+being+eaten%3F: https://www.inaturalist.org/terminology/field:id+meant+for+%2522eater%2522+or+organism+being+eaten%253F
field:url+for+%22partner%22+observation: https://www.inaturalist.org/terminology/field:url+for+%2522partner%2522+observation
field:is+observation+one+of+these+special+types+of+feeding%3F: https://www.inaturalist.org/terminology/field:is+observation+one+of+these+special+types+of+feeding%253F

For more information about column headers, see https://www.inaturalist.org/terminology

