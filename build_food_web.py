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
ZOOM_EXTENT = [0.005, 8]

# Extended qualitative palette (20 distinct colors)
CATEGORY_DEFINITIONS = {
    'plants': {
        'label': 'Plants & Fungi',
        'color': '#9BD6A5',
        'iconic_taxa': ['Plantae', 'Fungi'],
    },
    'vertebrates': {
        'label': 'Vertebrates',
        'color': '#8FBCEA',
        'iconic_taxa': ['Actinopterygii', 'Amphibia', 'Reptilia', 'Aves', 'Mammalia'],
    },
    'invertebrates': {
        'label': 'Invertebrates',
        'color': '#F5B97B',
        'iconic_taxa': ['Insecta', 'Arachnida', 'Mollusca', 'Protozoa', 'Animalia', 'Chromista'],
    },
    'unknown': {
        'label': 'Other',
        'color': '#C8C8C8',
        'iconic_taxa': [],
    },
}
UNKNOWN_COLOR = CATEGORY_DEFINITIONS['unknown']['color']

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
      .zoom-panel {
        position: absolute;
        top: 1rem;
        right: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        z-index: 10;
      }
      .zoom-panel button {
        border: 1px solid rgba(148, 163, 184, 0.6);
        border-radius: 0.5rem;
        padding: 0.4rem 0.6rem;
        background: rgba(255, 255, 255, 0.92);
        color: #0f172a;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.15);
      }
      .zoom-panel button:hover {
        background: #ffffff;
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
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        font-size: 0.75rem;
        max-height: 14rem;
        overflow-y: auto;
      }
      .label-options {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        margin-top: 0.5rem;
        font-size: 0.85rem;
      }
      .label-options label {
        display: flex;
        align-items: center;
        gap: 0.4rem;
      }
      .legend-item {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
      }
      .legend-color {
        width: 0.75rem;
        height: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid rgba(15, 23, 42, 0.15);
      }
      .legend-info {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
      }
      .legend-label {
        font-weight: 600;
        color: #0f172a;
      }
      .legend-taxa {
        color: #475569;
        font-size: 0.68rem;
        line-height: 1.3;
      }
      .legend::-webkit-scrollbar {
        width: 0.4rem;
      }
      .legend::-webkit-scrollbar-thumb {
        background: rgba(100, 116, 139, 0.4);
        border-radius: 1rem;
      }
      .download-btn {
        margin-top: 0.5rem;
        border: 1px solid rgba(148, 163, 184, 0.6);
        border-radius: 0.5rem;
        padding: 0.4rem 0.6rem;
        background: rgba(255, 255, 255, 0.92);
        color: #0f172a;
        font-weight: 600;
        cursor: pointer;
        box-shadow: 0 5px 15px rgba(15, 23, 42, 0.12);
      }
      .download-btn:hover {
        background: #ffffff;
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
      .tooltip-sci {
        font-size: 0.68rem;
        color: #cbd5f5;
        font-style: italic;
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
          <input id=\"searchBox\" placeholder=\"Search by common or scientific name\" />
          <button id=\"searchButton\">Go</button>
        </div>
        <div class=\"legend\" id=\"legend\"></div>
        <div class=\"label-options\">
          <label><input type=\"checkbox\" id=\"toggleCommon\" checked /> Common names</label>
          <label><input type=\"checkbox\" id=\"toggleScientific\" /> Scientific names</label>
        </div>
        <button id=\"downloadNetworkBtn\" class=\"download-btn\">Download network</button>
      </div>
      <div class=\"zoom-panel\">
        <button id=\"zoomInBtn\" aria-label=\"Zoom in\">+</button>
        <button id=\"zoomOutBtn\" aria-label=\"Zoom out\">-</button>
        <button id=\"fullscreenToggle\" aria-label=\"Toggle full screen\"></button>
      </div>
      <svg id=\"network\"></svg>
      <div class=\"tooltip\" id=\"tooltip\"></div>
    </div>
    <script>
      const graphData = __GRAPH_DATA__;
      const categoryColors = __CATEGORY_COLORS__;
      const legendItems = __LEGEND_ITEMS__;
      const dpr = window.devicePixelRatio || 1;

      const svg = d3.select('#network');
      const tooltip = d3.select('#tooltip');
      const containerEl = document.getElementById('graph-container');
      let showCommonNames = true;
      let showScientificNames = false;

      const width = window.innerWidth;
      const height = window.innerHeight;

      svg.attr('viewBox', [0, 0, width, height]);

      const defs = svg.append('defs');
      defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 12)
        .attr('refY', 0)
        .attr('markerWidth', 8)
        .attr('markerHeight', 8)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', 'rgba(30, 41, 59, 0.65)');

      const projectLink = (source, target) => {
        if (!source || !target) {
          return { x1: 0, y1: 0, x2: 0, y2: 0 };
        }
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        const offsetX = (dx / distance) * {node_radius};
        const offsetY = (dy / distance) * {node_radius};
        return {
          x1: source.x + offsetX,
          y1: source.y + offsetY,
          x2: target.x - offsetX,
          y2: target.y - offsetY,
        };
      };

      const formatLabel = (node) => {
        const common = node.commonName || node.label;
        const scientific = node.scientificName;
        const parts = [];
        if (showCommonNames && common) {
          parts.push(common);
        }
        if (showScientificNames && scientific) {
          if (showCommonNames && common) {
            parts.push(`(${scientific})`);
          } else {
            parts.push(scientific);
          }
        }
        if (!parts.length) {
          return common || scientific || node.label || 'Unknown';
        }
        return parts.join(' ');
      };

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
        .attr('fill', d => (categoryColors[d.category]?.color) || '{unknown_color}');

      const labels = node.append('text')
        .attr('fill', '#0f172a')
        .attr('dy', '0.35em')
        .text(d => formatLabel(d));

      node.append('title')
        .text(d => {
          const group = categoryColors[d.category];
          const groupLabel = group?.label || 'Other';
          const taxaList = group?.taxa?.join(', ') || '—';
          return `${d.label}\nIconic taxon: ${d.iconicTaxon}\nGroup: ${groupLabel}\nIconic taxa in group: ${taxaList}`;
        });

      const updateLabelVisibility = (scale) => {
        const minScale = 0.15;
        const maxScale = 0.4;
        const clamped =
          scale <= minScale
            ? 0
            : scale >= maxScale
              ? 1
              : (scale - minScale) / (maxScale - minScale);
        labels.style('opacity', clamped);
      };

      const updateLabels = () => {
        labels.text(d => formatLabel(d));
      };

      updateLabels();
      updateLabelVisibility(1);

      node.on('mouseenter', (event, d) => {
        tooltip.style('opacity', 1)
          .html(`
            <strong>${d.commonName || d.label}</strong><br/>
            <span class="text-xs">${d.scientificName !== 'Unidentified' ? d.scientificName : ''}</span><br/>
            Class: ${d.className}
          `);
      }).on('mousemove', (event) => {
        const bounds = containerEl?.getBoundingClientRect();
        const baseX = event.clientX - (bounds?.left || 0);
        const baseY = event.clientY - (bounds?.top || 0);
        const tooltipWidth = tooltip.node()?.offsetWidth || 0;
        const tooltipHeight = tooltip.node()?.offsetHeight || 0;
        const limitX = bounds?.width || width;
        const limitY = bounds?.height || height;
        const posX = Math.min(Math.max(baseX + 16, 16), limitX - tooltipWidth - 16);
        const posY = Math.min(Math.max(baseY + 16, 16), limitY - tooltipHeight - 16);
        tooltip
          .style('left', `${posX}px`)
          .style('top', `${posY}px`);
      }).on('mouseleave', () => tooltip.style('opacity', 0));

      const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(65).strength(0.25))
        .force('charge', d3.forceManyBody().strength(-70))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide({node_radius} * 1.6));

      simulation.on('tick', () => {
        link
          .attr('x1', d => projectLink(d.source, d.target).x1)
          .attr('y1', d => projectLink(d.source, d.target).y1)
          .attr('x2', d => projectLink(d.source, d.target).x2)
          .attr('y2', d => projectLink(d.source, d.target).y2);

        node
          .attr('transform', d => `translate(${d.x},${d.y})`);

        labels
          .attr('x', d => (d.x >= width / 2 ? {node_radius} + 4 : -({node_radius} + 4)))
          .attr('text-anchor', d => (d.x >= width / 2 ? 'start' : 'end'));
      });

      const zoomBehaviour = d3.zoom()
        .scaleExtent({zoom_extent})
        .on('zoom', (event) => {
          zoomLayer.attr('transform', event.transform);
          updateLabelVisibility(event.transform.k);
        });

      svg.call(zoomBehaviour);

      const zoomBy = (factor) => {
        svg.transition().duration(250).call(zoomBehaviour.scaleBy, factor);
      };

      const zoomInBtn = document.getElementById('zoomInBtn');
      const zoomOutBtn = document.getElementById('zoomOutBtn');
      zoomInBtn?.addEventListener('click', () => zoomBy(1.2));
      zoomOutBtn?.addEventListener('click', () => zoomBy(1 / 1.2));

      window.addEventListener('message', (event) => {
        const { type } = event.data || {};
        if (type === 'zoomIn') {
          zoomBy(1.2);
        }
        if (type === 'zoomOut') {
          zoomBy(1 / 1.2);
        }
      });

      const fullscreenToggle = document.getElementById('fullscreenToggle');
      const updateFullscreenButton = () => {
        if (!fullscreenToggle) return;
        fullscreenToggle.textContent = document.fullscreenElement ? 'Exit full screen' : 'Full screen';
      };
      fullscreenToggle?.addEventListener('click', () => {
        if (!document.fullscreenElement) {
          containerEl?.requestFullscreen?.();
        } else {
          document.exitFullscreen?.();
        }
      });
      document.addEventListener('fullscreenchange', updateFullscreenButton);
      updateFullscreenButton();

      const toggleCommon = document.getElementById('toggleCommon');
      const toggleScientific = document.getElementById('toggleScientific');
      const downloadButton = document.getElementById('downloadNetworkBtn');

      const sanitizeFileName = (value) =>
        value.replace(/[\\/:*?"<>|]/g, '').trim() || 'who-eats-whom-network';

      const buildStandaloneHtml = () => {
        const clone = document.documentElement.cloneNode(true);
        if (!(clone instanceof HTMLElement)) {
          return document.documentElement.outerHTML;
        }
        const svg = clone.querySelector('#network');
        if (svg) {
          while (svg.firstChild) {
            svg.removeChild(svg.firstChild);
          }
        }
        const downloadBtn = clone.querySelector('#downloadNetworkBtn');
        downloadBtn?.parentElement?.removeChild(downloadBtn);
        return '<!DOCTYPE html>\\n' + clone.outerHTML;
      };

      const handleLabelToggle = (type, checked) => {
        if (type === 'common') {
          if (!checked && !showScientificNames) {
            toggleCommon.checked = true;
            return;
          }
          showCommonNames = checked;
        } else {
          if (!checked && !showCommonNames) {
            toggleScientific.checked = true;
            return;
          }
          showScientificNames = checked;
        }
        updateLabels();
      };

      toggleCommon?.addEventListener('change', (event) =>
        handleLabelToggle('common', event.target.checked)
      );
      toggleScientific?.addEventListener('change', (event) =>
        handleLabelToggle('scientific', event.target.checked)
      );
      downloadButton?.addEventListener('click', () => {
        const html = buildStandaloneHtml();
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${sanitizeFileName('who-eats-whom-network')}.html`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      });

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

      const findNodeMatch = (value) => {
        const term = value.trim().toLowerCase();
        if (!term) return null;
        return graphData.nodes.find((n) => {
          const candidates = [n.id, n.label, n.commonName, n.scientificName];
          return candidates.some(
            (entry) => typeof entry === 'string' && entry.toLowerCase() === term
          );
        });
      };

      function highlightNode(value) {
        const match = findNodeMatch(value);
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
      if (legend) {
        legend.innerHTML = '';
      }
      legendItems.forEach((entry) => {
        const item = document.createElement('div');
        item.className = 'legend-item';
        const swatch = document.createElement('span');
        swatch.className = 'legend-color';
        swatch.style.background = entry.color;

        const info = document.createElement('div');
        info.className = 'legend-info';

        const label = document.createElement('div');
        label.className = 'legend-label';
        label.textContent = entry.label;

        const taxa = document.createElement('div');
        taxa.className = 'legend-taxa';
        taxa.textContent = entry.taxa.join(', ');

        info.appendChild(label);
        info.appendChild(taxa);
        item.appendChild(swatch);
        item.appendChild(info);
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


PLANT_TAXA = set(CATEGORY_DEFINITIONS['plants']['iconic_taxa'])
VERTEBRATE_TAXA = set(CATEGORY_DEFINITIONS['vertebrates']['iconic_taxa'])
INVERTEBRATE_TAXA = set(CATEGORY_DEFINITIONS['invertebrates']['iconic_taxa'])


def map_iconic_to_category(iconic_taxon: str) -> str:
    """Map an iconic taxon name into one of the high-level categories."""
    if iconic_taxon in PLANT_TAXA:
        return 'plants'
    if iconic_taxon in VERTEBRATE_TAXA:
        return 'vertebrates'
    if iconic_taxon in INVERTEBRATE_TAXA:
        return 'invertebrates'
    return 'unknown'


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

    if 'scientific_name' not in df.columns:
        fallback = df.get('taxon_name')
        if fallback is not None:
            df['scientific_name'] = fallback
        else:
            df['scientific_name'] = df.get('taxon_species_name', 'Unidentified')

    info_columns = [
        'taxon_kingdom_name',
        'taxon_class_name',
        'url',
        'description',
        'iconic_taxon_name',
        'scientific_name',
    ]

    meta = (
        df.drop_duplicates('common_name')
        .set_index('common_name')[info_columns]
        .to_dict(orient='index')
    )

    nodes = []
    for name in sorted(nodes_in_edges):
        details = meta.get(name, {})
        iconic_taxon = details.get('iconic_taxon_name', 'Unidentified')
        category = map_iconic_to_category(iconic_taxon)
        scientific_name = (
            details.get('scientific_name')
            or details.get('taxon_name')
            or 'Unidentified'
        )
        nodes.append({
            'id': name,
            'label': name,
             'commonName': name,
             'scientificName': scientific_name,
            'kingdom': details.get('taxon_kingdom_name', 'Unidentified'),
            'className': details.get('taxon_class_name', 'Unidentified'),
            'url': details.get('url', 'Unidentified'),
            'description': details.get('description', 'Unidentified'),
            'iconicTaxon': iconic_taxon,
            'category': category,
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

    category_taxa_map = {}
    for node in graph['nodes']:
        category_taxa_map.setdefault(node['category'], set()).add(node['iconicTaxon'])

    category_colors = {}
    legend_items = []
    category_order = ['plants', 'vertebrates', 'invertebrates', 'unknown']
    for category_key in category_order:
        taxa_for_category = sorted(category_taxa_map.get(category_key, []))
        if not taxa_for_category:
            continue
        config = CATEGORY_DEFINITIONS[category_key]
        category_colors[category_key] = {
            'color': config['color'],
            'label': config['label'],
            'taxa': taxa_for_category,
        }
        legend_items.append({
            'label': config['label'],
            'color': config['color'],
            'taxa': taxa_for_category,
        })

    stats = {
        'observations': len(df),
        'edges': len(graph['links']),
        'taxa': len(graph['nodes']),
        'locations': len(unique_locations),
    }

    html_content = (
        HTML_TEMPLATE
        .replace('__GRAPH_DATA__', json.dumps(graph_json))
        .replace('__CATEGORY_COLORS__', json.dumps(category_colors))
        .replace('__LEGEND_ITEMS__', json.dumps(legend_items))
        .replace('{node_radius}', str(NODE_RADIUS))
        .replace('{edge_base_width}', str(EDGE_BASE_WIDTH))
        .replace('{zoom_extent}', json.dumps(ZOOM_EXTENT))
        .replace('{unknown_color}', UNKNOWN_COLOR)
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
