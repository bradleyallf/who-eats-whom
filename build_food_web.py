import json
from collections import Counter
from pathlib import Path

import pandas as pd

# Paths
REPO_ROOT = Path(__file__).parent
PUBLIC_DIR = REPO_ROOT / 'public'
OUTPUT_HTML = REPO_ROOT / 'predator_prey.html'
PUBLIC_HTML = PUBLIC_DIR / 'predator_prey.html'

# Styling constants
NODE_RADIUS = 8
EDGE_BASE_WIDTH = 0.03
ZOOM_EXTENT = [0.1, 5]

# Extended qualitative palette (20 distinct colors)
COLOR_PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2',
    '#7f7f7f', '#bcbd22', '#17becf', '#393b79', '#637939', '#8c6d31', '#843c39',
    '#7b4173', '#3182bd', '#e6550d', '#31a354', '#756bb1', '#636363'
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Who Eats Whom – Predator/Prey Network</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <script src=\"https://d3js.org/d3.v7.min.js\"></script>
    <style>
      :root {
        color-scheme: light;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }
      body {
        margin: 0;
        background: #f8fafc;
        color: #0f172a;
      }
      #graph-container {
        position: relative;
        width: 100vw;
        height: 100vh;
        overflow: hidden;
      }
      svg {
        width: 100%;
        height: 100%;
        cursor: grab;
        background: white;
      }
      svg:active {
        cursor: grabbing;
      }
      .controls {
        position: absolute;
        top: 1rem;
        left: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        background: rgba(255, 255, 255, 0.92);
        border-radius: 0.75rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
        max-width: min(22rem, 80vw);
        z-index: 10;
      }
      .controls h1 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 700;
      }
      .controls p {
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.4;
        color: #334155;
      }
      .search {
        display: flex;
        gap: 0.35rem;
      }
      .search input {
        flex: 1;
        padding: 0.4rem 0.6rem;
        border-radius: 0.5rem;
        border: 1px solid #cbd5f5;
        font-size: 0.9rem;
      }
      .search button {
        padding: 0.4rem 0.8rem;
        border-radius: 0.5rem;
        border: none;
        background: #f97316;
        color: white;
        font-weight: 600;
        cursor: pointer;
      }
      .legend {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
        gap: 0.35rem 0.75rem;
        font-size: 0.75rem;
        max-height: 12rem;
        overflow-y: auto;
      }
      .legend-item {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        white-space: nowrap;
      }
      .legend-color {
        width: 0.75rem;
        height: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid rgba(15, 23, 42, 0.15);
      }
      .legend::-webkit-scrollbar {
        width: 0.4rem;
      }
      .legend::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.4);
        border-radius: 1rem;
      }
      .tooltip {
        position: absolute;
        pointer-events: none;
        padding: 0.5rem 0.7rem;
        font-size: 0.75rem;
        background: rgba(15, 23, 42, 0.92);
        color: white;
        border-radius: 0.5rem;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.35);
        max-width: 16rem;
        opacity: 0;
        transition: opacity 120ms ease-out;
        z-index: 20;
      }
      .node circle {
        stroke: white;
        stroke-width: 1.5px;
      }
      .node text {
        font-size: 0.7rem;
        pointer-events: none;
        text-shadow: 0 1px 2px rgba(15, 23, 42, 0.25);
      }
      .node.highlight circle {
        stroke: #f97316;
        stroke-width: 3px;
      }
      .link {
        stroke: rgba(30, 41, 59, 0.35);
        stroke-opacity: 0.7;
      }
      .link.highlight {
        stroke: #f97316;
        stroke-opacity: 0.9;
      }
    </style>
  </head>
  <body>
    <div id=\"graph-container\">
      <div class=\"controls\">
        <h1>Predator/Prey Network</h1>
        <p>Arrows run from prey → predator. Edge thickness shows how many observations recorded that interaction.</p>
        <div class=\"search\">
          <input id=\"searchBox\" placeholder=\"Search by common name\" />
          <button id=\"searchButton\">Go</button>
        </div>
        <div class=\"legend\" id=\"legend\"></div>
      </div>
      <svg id=\"network\"></svg>
      <div class=\"tooltip\" id=\"tooltip\"></div>
    </div>
    <script>
      const graphData = __GRAPH_DATA__;
      const colorMap = __COLOR_MAP__;
      const dpr = window.devicePixelRatio || 1;

      const svg = d3.select('#network');
      const tooltip = d3.select('#tooltip');

      const width = window.innerWidth;
      const height = window.innerHeight;

      svg.attr('viewBox', [0, 0, width, height]);

      const defs = svg.append('defs');
      defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 16)
        .attr('refY', 0)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', 'rgba(30, 41, 59, 0.65)');

      const zoomLayer = svg.append('g');

      const link = zoomLayer.append('g')
        .attr('stroke-linecap', 'round')
        .selectAll('line')
        .data(graphData.links)
        .join('line')
        .attr('class', 'link')
        .attr('stroke-width', d => Math.max({edge_base_width} + d.count, 0.75))
        .attr('marker-end', 'url(#arrowhead)');

      const node = zoomLayer.append('g')
        .selectAll('g')
        .data(graphData.nodes)
        .join('g')
        .attr('class', 'node')
        .call(d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended));

      node.append('circle')
        .attr('r', {node_radius})
        .attr('fill', d => colorMap[d.iconicTaxon] || '#94a3b8');

      node.append('text')
        .attr('x', {node_radius} + 3)
        .attr('y', 3)
        .attr('fill', '#0f172a')
        .text(d => d.label);

      node.append('title')
        .text(d => `${d.label}\nIconic taxon: ${d.iconicTaxon}`);

      node.on('mouseenter', (event, d) => {
        tooltip.style('opacity', 1)
          .html(`
            <strong>${d.label}</strong><br/>
            Iconic taxon: ${d.iconicTaxon}<br/>
            Kingdom: ${d.kingdom}<br/>
            Class: ${d.className}<br/>
            ${d.description !== 'Unidentified' ? `Description: ${d.description}<br/>` : ''}
            ${d.url !== 'Unidentified' ? `<a href="${d.url}" target="_blank" rel="noopener noreferrer">View observation</a>` : ''}
          `);
      }).on('mousemove', (event) => {
        const [x, y] = d3.pointer(event);
        tooltip
          .style('left', `${x + 20}px`)
          .style('top', `${y + 20}px`);
      }).on('mouseleave', () => tooltip.style('opacity', 0));

      const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(80).strength(0.2))
        .force('charge', d3.forceManyBody().strength(-80))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide({node_radius} * 1.8));

      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);

        node
          .attr('transform', d => `translate(${d.x},${d.y})`);
      });

      const zoomBehaviour = d3.zoom()
        .scaleExtent({zoom_extent})
        .on('zoom', (event) => {
          zoomLayer.attr('transform', event.transform);
        });

      svg.call(zoomBehaviour);

      const searchInput = document.getElementById('searchBox');
      const searchButton = document.getElementById('searchButton');

      function clearHighlights() {
        node.classed('highlight', false);
        link.classed('highlight', false);
      }

      function focusNode(nodeData) {
        const scale = 1.6;
        const transform = d3.zoomIdentity
          .translate(width / 2, height / 2)
          .scale(scale)
          .translate(-nodeData.x, -nodeData.y);

        svg.transition().duration(650).call(zoomBehaviour.transform, transform);
      }

      function highlightNode(value) {
        const term = value.trim().toLowerCase();
        if (!term) {
          clearHighlights();
          return;
        }
        const match = graphData.nodes.find((n) => n.id.toLowerCase() === term);
        clearHighlights();
        if (match) {
          node.filter(d => d.id === match.id).classed('highlight', true);
          link.filter(d => d.source.id === match.id || d.target.id === match.id)
            .classed('highlight', true);
          focusNode(match);
        } else {
          alert(`No match found for "${value}"`);
        }
      }

      searchButton.addEventListener('click', () => highlightNode(searchInput.value));
      searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          highlightNode(searchInput.value);
        }
        if (event.key === 'Escape') {
          clearHighlights();
          searchInput.value = '';
        }
      });

      const legend = document.getElementById('legend');
      Object.entries(colorMap).forEach(([taxon, color]) => {
        const item = document.createElement('div');
        item.className = 'legend-item';
        item.innerHTML = `<span class=\"legend-color\" style=\"background:${color}\"></span> ${taxon}`;
        legend.appendChild(item);
      });

      function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      }

      function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
      }

      function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }

      window.addEventListener('resize', () => {
        const newWidth = window.innerWidth;
        const newHeight = window.innerHeight;
        svg.attr('viewBox', [0, 0, newWidth, newHeight]);
        simulation.force('center', d3.forceCenter(newWidth / 2, newHeight / 2));
        simulation.alphaTarget(0.1).restart();
        setTimeout(() => simulation.alphaTarget(0), 500);
      });
    </script>
  </body>
</html>
"""


def build_color_map(unique_iconic_taxa):
    """Assign a deterministic color to each iconic taxon name."""
    mapping = {}
    for idx, taxon in enumerate(sorted(unique_iconic_taxa)):
        color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]
        mapping[taxon] = color
    return mapping


def create_graph(df: pd.DataFrame):
    """Create nodes and links suitable for the D3 visualization."""
    edge_list = []

    # Map observation ID -> common name
    df['id_str'] = df['id'].astype(str)
    id_to_name = dict(zip(df['id_str'], df['common_name']))

    for _, row in df.iterrows():
        role = row['field:id meant for "eater" or organism being eaten?']
        this_name = row['common_name']
        partner_id = row['partner_id']

        if not isinstance(role, str) or not partner_id or not isinstance(this_name, str):
            continue

        partner_name = id_to_name.get(partner_id)
        if not isinstance(partner_name, str):
            continue

        role_lc = role.strip().lower()
        if role_lc != 'eater':
            continue

        predator = this_name
        prey = partner_name
        edge_list.append((predator, prey))

    if not edge_list:
        raise ValueError('No predator/prey edges were generated. Check the input data.')

    edge_counts = Counter(edge_list)
    edges = list(edge_counts.keys())

    nodes_in_edges = {name for edge in edges for name in edge}

    info_columns = [
        'taxon_kingdom_name',
        'taxon_class_name',
        'url',
        'description',
        'iconic_taxon_name',
    ]

    meta = (
        df.drop_duplicates('common_name')
        .set_index('common_name')[info_columns]
        .to_dict(orient='index')
    )

    nodes = []
    for name in sorted(nodes_in_edges):
        details = meta.get(name, {})
        nodes.append({
            'id': name,
            'label': name,
            'kingdom': details.get('taxon_kingdom_name', 'Unidentified'),
            'className': details.get('taxon_class_name', 'Unidentified'),
            'url': details.get('url', 'Unidentified'),
            'description': details.get('description', 'Unidentified'),
            'iconicTaxon': details.get('iconic_taxon_name', 'Unidentified'),
        })

    links = []
    for predator, prey in edges:
        count = edge_counts[(predator, prey)]
        links.append({
            'source': prey,  # prey → predator direction
            'target': predator,
            'count': count,
        })

    return {'nodes': nodes, 'links': links, 'edge_counts': edge_counts}


def main():
    df = pd.read_csv(REPO_ROOT / 'observations.csv', low_memory=False)
    print('Original rows:', df.shape[0])
    print('Unique countries:', df['place_country_name'].nunique())

    unique_roles = df['field:id meant for "eater" or organism being eaten?'].unique()
    print('Unique predator/prey role labels:', unique_roles)

    unique_cols = [col for col in df.columns if df[col].is_unique]
    print('Columns with unique values:', unique_cols)

    df = df[df['quality_grade'] == 'research'].reset_index(drop=True)
    print('Rows after filtering research grade:', df.shape[0])

    def extract_partner_id(url_str):
        if not isinstance(url_str, str) or '/observations/' not in url_str:
            return None
        return url_str.rstrip('/').split('/')[-1]

    df['partner_id'] = df['field:url for "partner" observation'].apply(extract_partner_id)

    df = df[df['common_name'].notna()].reset_index(drop=True)

    unique_locations = {
        (row.get('place_country_name') or '').strip()
        for _, row in df.iterrows()
        if isinstance(row.get('place_country_name'), str) and row.get('place_country_name').strip()
    }

    fill_columns = [
        'taxon_kingdom_name',
        'taxon_class_name',
        'url',
        'description',
        'iconic_taxon_name',
    ]
    df[fill_columns] = df[fill_columns].fillna('Unidentified')

    graph = create_graph(df)
    graph_json = {'nodes': graph['nodes'], 'links': graph['links']}

    unique_taxa = {node['iconicTaxon'] for node in graph['nodes']}
    color_map = build_color_map(unique_taxa)

    stats = {
        'observations': len(df),
        'edges': len(graph['links']),
        'taxa': len(graph['nodes']),
        'locations': len(unique_locations),
    }

    html_content = (
        HTML_TEMPLATE
        .replace('__GRAPH_DATA__', json.dumps(graph_json))
        .replace('__COLOR_MAP__', json.dumps(color_map))
        .replace('{node_radius}', str(NODE_RADIUS))
        .replace('{edge_base_width}', str(EDGE_BASE_WIDTH))
        .replace('{zoom_extent}', json.dumps(ZOOM_EXTENT))
    )

    OUTPUT_HTML.write_text(html_content, encoding='utf-8')
    print(f'Wrote D3 visualization to {OUTPUT_HTML}')

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_HTML.write_text(html_content, encoding='utf-8')
    print(f'Copied visualization to {PUBLIC_HTML}')

    stats_path = PUBLIC_DIR / 'predator_prey_stats.json'
    stats_path.write_text(json.dumps(stats, indent=2), encoding='utf-8')
    print(f'Wrote stats to {stats_path}')


if __name__ == '__main__':
    main()
