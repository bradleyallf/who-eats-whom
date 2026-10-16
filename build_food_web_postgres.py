"""Refresh the graph data inside the existing predator_prey.html from Postgres.

Unlike build_food_web.py, this does NOT rebuild the page from a template.
It keeps your current HTML (including any click-to-dim or other custom
behaviour) and only replaces these three lines:

    const graphData = ...;
    const categoryColors = ...;
    const legendItems = ...;

A .bak copy of each file is saved next to it before it is changed.

Run from the repo root:

    python3 build_food_web_postgres.py

Environment variables (both optional):
    POSTGRES_DSN          default postgresql://whodba:whopass@localhost:5433/who_eats_whom
    ACTIVE_ETL_VERSIONS   default "local-dev,2026-08-26-api" (same as backend/main.py)
"""

import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).parent
PUBLIC_DIR = REPO_ROOT / "public"
TARGETS = [PUBLIC_DIR / "predator_prey.html", REPO_ROOT / "predator_prey.html"]

DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://whodba:whopass@localhost:5433/who_eats_whom",
)
ACTIVE_ETL_VERSIONS = [
    v.strip()
    for v in os.getenv("ACTIVE_ETL_VERSIONS", "local-dev,2026-08-26-api").split(",")
    if v.strip()
]

CATEGORY_DEFINITIONS = {
    "plants": {
        "label": "Plants & Fungi",
        "color": "#9BD6A5",
        "iconic_taxa": ["Plantae", "Fungi"],
    },
    "vertebrates": {
        "label": "Vertebrates",
        "color": "#8FBCEA",
        "iconic_taxa": ["Actinopterygii", "Amphibia", "Reptilia", "Aves", "Mammalia"],
    },
    "invertebrates": {
        "label": "Invertebrates",
        "color": "#F5B97B",
        "iconic_taxa": ["Insecta", "Arachnida", "Mollusca", "Protozoa", "Animalia", "Chromista"],
    },
}


def map_iconic_to_category(iconic_taxon):
    for key, cfg in CATEGORY_DEFINITIONS.items():
        if iconic_taxon in cfg["iconic_taxa"]:
            return key
    return "unknown"


def fetch_data():
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.predator_taxon_id,
                       a.prey_taxon_id,
                       SUM(a.interaction_count)::int AS cnt
                FROM predator_prey_aggregates a
                JOIN etl_versions e ON e.id = a.etl_version_id
                WHERE e.version = ANY(%s)
                GROUP BY a.predator_taxon_id, a.prey_taxon_id
                """,
                (ACTIVE_ETL_VERSIONS,),
            )
            edge_rows = cur.fetchall()

            taxon_ids = sorted({t for r in edge_rows for t in (r[0], r[1])})
            cur.execute(
                """
                SELECT taxon_id, common_name, scientific_name,
                       iconic_taxon_name, kingdom, class_name
                FROM species
                WHERE taxon_id = ANY(%s)
                """,
                (taxon_ids,),
            )
            species = {
                r[0]: {
                    "common_name": r[1],
                    "scientific_name": r[2],
                    "iconic_taxon_name": r[3],
                    "kingdom": r[4],
                    "class_name": r[5],
                }
                for r in cur.fetchall()
            }

            cur.execute(
                """
                SELECT COUNT(DISTINCT o.raw->>'place_country_name')
                FROM observations o
                JOIN etl_versions e ON e.id = o.etl_version_id
                WHERE e.version = ANY(%s)
                  AND o.quality_grade = 'research'
                  AND COALESCE(o.raw->>'place_country_name', '') <> ''
                """,
                (ACTIVE_ETL_VERSIONS,),
            )
            locations = cur.fetchone()[0]

    return edge_rows, species, locations


def build_graph(edge_rows, species):
    counts = defaultdict(int)
    node_info = {}

    for predator_id, prey_id, cnt in edge_rows:
        pred = species.get(predator_id)
        prey = species.get(prey_id)
        if not pred or not prey:
            continue
        pred_name = (pred["common_name"] or "").strip()
        prey_name = (prey["common_name"] or "").strip()
        if not pred_name or not prey_name:
            continue
        counts[(pred_name, prey_name)] += cnt
        node_info.setdefault(pred_name, (predator_id, pred))
        node_info.setdefault(prey_name, (prey_id, prey))

    if not counts:
        raise SystemExit("No predator/prey edges found in Postgres. Nothing written.")

    nodes = []
    for name in sorted(node_info):
        taxon_id, sp = node_info[name]
        iconic = sp["iconic_taxon_name"] or "Unidentified"
        nodes.append({
            "id": name,
            "label": name,
            "commonName": name,
            "scientificName": sp["scientific_name"] or "Unidentified",
            "kingdom": sp["kingdom"] or "Unidentified",
            "className": sp["class_name"] or "Unidentified",
            "url": f"https://www.inaturalist.org/taxa/{taxon_id}",
            "description": "Unidentified",
            "iconicTaxon": iconic,
            "category": map_iconic_to_category(iconic),
        })

    links = [
        {"source": prey, "target": pred, "count": cnt}
        for (pred, prey), cnt in counts.items()
    ]
    return {"nodes": nodes, "links": links}


def build_legend(nodes):
    category_taxa = defaultdict(set)
    for n in nodes:
        category_taxa[n["category"]].add(n["iconicTaxon"])

    category_colors = {}
    legend_items = []
    for key in ["plants", "vertebrates", "invertebrates"]:
        taxa = sorted(category_taxa.get(key, []))
        if not taxa:
            continue
        cfg = CATEGORY_DEFINITIONS[key]
        category_colors[key] = {"color": cfg["color"], "label": cfg["label"], "taxa": taxa}
        legend_items.append({"label": cfg["label"], "color": cfg["color"], "taxa": taxa})
    return category_colors, legend_items


def dumps(value):
    # Single line, and safe to embed inside a <script> tag.
    return json.dumps(value).replace("</", "<\\/")


def replace_const(html, name, value):
    pattern = re.compile(rf"^([ \t]*const {name} = ).*;[ \t]*$", re.MULTILINE)
    new_html, n = pattern.subn(lambda m: f"{m.group(1)}{dumps(value)};", html)
    if n != 1:
        raise ValueError(f"expected exactly one 'const {name} = ...;' line, found {n}")
    return new_html


def main():
    print(f"Reading ETL versions: {', '.join(ACTIVE_ETL_VERSIONS)}")
    edge_rows, species, locations = fetch_data()
    graph = build_graph(edge_rows, species)
    category_colors, legend_items = build_legend(graph["nodes"])

    updated = 0
    for path in TARGETS:
        if not path.exists():
            print(f"Skipping (not found): {path}")
            continue
        html = path.read_text(encoding="utf-8")
        try:
            html = replace_const(html, "graphData", graph)
            html = replace_const(html, "categoryColors", category_colors)
            html = replace_const(html, "legendItems", legend_items)
        except ValueError as exc:
            print(f"Skipping {path}: {exc}")
            continue
        shutil.copy2(path, path.with_suffix(".html.bak"))
        path.write_text(html, encoding="utf-8")
        print(f"Updated {path}")
        updated += 1

    if not updated:
        raise SystemExit("No HTML file was updated.")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    stats = {
        "observations": sum(link["count"] for link in graph["links"]),
        "edges": len(graph["links"]),
        "taxa": len(graph["nodes"]),
        "locations": locations,
    }
    (PUBLIC_DIR / "predator_prey_stats.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8"
    )
    print(f"Nodes: {len(graph['nodes'])}, links: {len(graph['links'])}")


if __name__ == "__main__":
    main()