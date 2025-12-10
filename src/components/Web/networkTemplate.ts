const NETWORK_HTML_TEMPLATE = String.raw`<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Who Eats Whom – Predator/Prey Network</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="https://d3js.org/d3.v7.min.js"></script>
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
      .legend {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        font-size: 0.75rem;
        max-height: 14rem;
        overflow-y: auto;
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
        gap: 0.35rem;
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
    <div id="graph-container">
      <div class="controls">
        <h1>Predator/Prey Network</h1>
        <p>Arrows run from prey → predator. Edge thickness shows how many observations recorded that interaction.</p>
        <div class="search">
          <input id="searchBox" placeholder="Search by common or scientific name" />
          <button id="searchButton">Go</button>
        </div>
        <div class="legend" id="legend"></div>
        <div class="label-options">
          <label><input type="checkbox" id="toggleCommon" checked /> Common names</label>
          <label><input type="checkbox" id="toggleScientific" checked /> Scientific names</label>
        </div>
        <button id="downloadNetworkBtn" class="download-btn">Download network</button>
      </div>
      <div class="zoom-panel">
        <button id="zoomInBtn" aria-label="Zoom in">+</button>
        <button id="zoomOutBtn" aria-label="Zoom out">-</button>
        <button id="fullscreenToggle" aria-label="Toggle full screen"></button>
      </div>
      <svg id="network"></svg>
      <div class="tooltip" id="tooltip"></div>
    </div>
    <script>
      const graphData = __GRAPH_DATA__;
      const categoryColors = __CATEGORY_COLORS__;
      const legendItems = __LEGEND_ITEMS__;

      const svg = d3.select('#network');
      const tooltip = d3.select('#tooltip');
      const containerEl = document.getElementById('graph-container');
      let showCommonNames = true;
      let showScientificNames = true;

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
        const offsetX = (dx / distance) * 8;
        const offsetY = (dy / distance) * 8;
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
        if (showCommonNames && common) parts.push(common);
        if (showScientificNames && scientific) {
          if (showCommonNames && common) parts.push('(' + scientific + ')');
          else parts.push(scientific);
        }
        if (!parts.length) return common || scientific || node.label || 'Unknown';
        return parts.join(' ');
      };

      const zoomLayer = svg.append('g');

      const link = zoomLayer.append('g')
        .attr('stroke-linecap', 'round')
        .selectAll('line')
        .data(graphData.links)
        .join('line')
        .attr('class', 'link')
        .attr('stroke-width', d => Math.max(0.03 + d.count, 0.75))
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
        .attr('r', 8)
        .attr('fill', d => (categoryColors[d.category]?.color) || '#C8C8C8');

      const labels = node.append('text')
        .attr('fill', '#0f172a')
        .attr('dy', '0.35em')
        .text(d => formatLabel(d));

      const updateLabelVisibility = (scale) => {
        const minScale = 0.1;
        const maxScale = 0.3;
        const clamped =
          scale <= minScale
            ? 0
            : scale >= maxScale
              ? 1
              : (scale - minScale) / (maxScale - minScale);
        labels.attr('fill-opacity', clamped);
      };

      const updateLabels = () => {
        labels.text(d => formatLabel(d));
      };

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
        if (Array.isArray(entry.taxa) && entry.taxa.length) {
          taxa.textContent = entry.taxa.join(', ');
        } else {
          taxa.textContent = '—';
        }
        info.appendChild(label);
        info.appendChild(taxa);
        item.appendChild(swatch);
        item.appendChild(info);
        legend?.appendChild(item);
      });

      node.on('mouseenter', (event, d) => {
        tooltip.style('opacity', 1)
          .html(\`
            <strong>\${d.commonName || d.label}</strong><br/>
            <span class=\"tooltip-sci\">\${d.scientificName || ''}</span><br/>
            Class: \${d.className}
          \`);
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
          .style('left', \`\${posX}px\`)
          .style('top', \`\${posY}px\`);
      }).on('mouseleave', () => tooltip.style('opacity', 0));

      const simulation = d3.forceSimulation(graphData.nodes)
        .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(65).strength(0.25))
        .force('charge', d3.forceManyBody().strength(-70))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide(8 * 1.6));

      simulation.on('tick', () => {
        link
          .attr('x1', d => projectLink(d.source, d.target).x1)
          .attr('y1', d => projectLink(d.source, d.target).y1)
          .attr('x2', d => projectLink(d.source, d.target).x2)
          .attr('y2', d => projectLink(d.source, d.target).y2);

        node
          .attr('transform', d => \`translate(\${d.x},\${d.y})\`);

        labels
          .attr('x', d => (d.x >= width / 2 ? 12 : -12))
          .attr('text-anchor', d => (d.x >= width / 2 ? 'start' : 'end'));
      });

      const zoomBehaviour = d3.zoom()
        .scaleExtent([0.005, 8])
        .on('zoom', (event) => {
          zoomLayer.attr('transform', event.transform);
          updateLabelVisibility(event.transform.k);
        });

      svg.call(zoomBehaviour);
      updateLabelVisibility(1);

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

      const zoomBy = (factor) => {
        svg.transition().duration(250).call(zoomBehaviour.scaleBy, factor);
      };

      const zoomInBtn = document.getElementById('zoomInBtn');
      const zoomOutBtn = document.getElementById('zoomOutBtn');
      zoomInBtn?.addEventListener('click', () => zoomBy(1.2));
      zoomOutBtn?.addEventListener('click', () => zoomBy(1 / 1.2));

      const handleNameToggle = (type, checked) => {
        if (type === 'common') {
          if (!checked && !showScientificNames) {
            document.getElementById('toggleCommon').checked = true;
            return;
          }
          showCommonNames = checked;
        } else {
          if (!checked && !showCommonNames) {
            document.getElementById('toggleScientific').checked = true;
            return;
          }
          showScientificNames = checked;
        }
        updateLabels();
      };

      document.getElementById('toggleCommon')?.addEventListener('change', (event) => {
        handleNameToggle('common', event.target.checked);
      });
      document.getElementById('toggleScientific')?.addEventListener('change', (event) => {
        handleNameToggle('scientific', event.target.checked);
      });

      const buildStandaloneHtml = () => {
        const clone = document.documentElement.cloneNode(true)
        if (!(clone instanceof HTMLElement)) {
          return document.documentElement.outerHTML
        }
        const svg = clone.querySelector('#network')
        if (svg) {
          while (svg.firstChild) {
            svg.removeChild(svg.firstChild)
          }
        }
        const downloadBtn = clone.querySelector('#downloadNetworkBtn')
        downloadBtn?.parentElement?.removeChild(downloadBtn)
        return '<!DOCTYPE html>\\n' + clone.outerHTML
      }

      const downloadBtn = document.getElementById('downloadNetworkBtn');
      downloadBtn?.addEventListener('click', () => {
        const html = buildStandaloneHtml();
        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const linkEl = document.createElement('a');
        linkEl.href = url;
        linkEl.download = 'who-eats-whom-network.html';
        document.body.appendChild(linkEl);
        linkEl.click();
        document.body.removeChild(linkEl);
        URL.revokeObjectURL(url);
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

      const searchInput = document.getElementById('searchBox');
      const searchButton = document.getElementById('searchButton');

      function clearHighlights() {
        d3.selectAll('.node').classed('highlight', false);
        d3.selectAll('.link').classed('highlight', false);
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
          link.filter(d => {
            const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
            const targetId = typeof d.target === 'object' ? d.target.id : d.target;
            return sourceId === match.id || targetId === match.id;
          }).classed('highlight', true);
          focusNode(match);
        } else {
          alert(\`No match found for "\${value}"\`);
        }
      }

      searchButton?.addEventListener('click', () => highlightNode(searchInput.value));
      searchInput?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          highlightNode(searchInput.value);
        }
        if (event.key === 'Escape') {
          clearHighlights();
          searchInput.value = '';
        }
      });
    </script>
  </body>
</html>`;

export interface DownloadableGraph {
  nodes: Array<Record<string, unknown>>;
  links: Array<Record<string, unknown>>;
}

export const generateNetworkHtml = (
  graphData: DownloadableGraph,
  categoryColors: Record<string, { color: string; label: string }>,
  legendItems: Array<{ label: string; color: string; taxa?: string[] }>
) => {
  return NETWORK_HTML_TEMPLATE.replace('__GRAPH_DATA__', JSON.stringify(graphData))
    .replace('__CATEGORY_COLORS__', JSON.stringify(categoryColors))
    .replace('__LEGEND_ITEMS__', JSON.stringify(legendItems));
};
