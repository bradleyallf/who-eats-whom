import { useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import { Observation, Ofv } from './types'
import { NETWORK_LEGEND, getCategoryColor, getTaxonCategory } from './networkColors'

interface Props {
  results: Observation[]
  partnerData: Record<string, Observation>
  type: Ofv['value']
  focalName: string
}

interface NodeDatum {
  id: string
  label: string
  commonName?: string
  scientificName?: string
  isFocal: boolean
  iconicTaxon: string
  category: string
  labelWidth?: number
  x?: number
  y?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

interface LinkDatum {
  source: string | NodeDatum
  target: string | NodeDatum
  count: number
}

const getCommonName = (observation?: Observation) =>
  observation?.taxon.preferred_common_name

const getScientificName = (observation?: Observation) =>
  observation?.taxon.name

const getDisplayName = (observation?: Observation) => {
  if (!observation) return undefined
  return (
    observation.taxon.preferred_common_name ||
    observation.taxon.name ||
    undefined
  )
}

const labelsMatch = (a: string, b: string) =>
  a.localeCompare(b, undefined, { sensitivity: 'base' }) === 0

const getIconicTaxon = (observation?: Observation) =>
  observation?.taxon.iconic_taxon_name || 'Unidentified'

const getNodeRadius = (node: NodeDatum) => (node.isFocal ? 12 : 9)

export const SearchResultNetwork = (props: Props) => {
  const { results, partnerData, type, focalName } = props
  const svgRef = useRef<SVGSVGElement | null>(null)
  const zoomBehaviourRef = useRef<any>(null)
  const svgSelectionRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [isFullScreen, setIsFullScreen] = useState(false)
  const [showCommonNames, setShowCommonNames] = useState(true)
  const [showScientificNames, setShowScientificNames] = useState(false)

  const formatNodeLabelText = (node: NodeDatum) => {
    const parts: string[] = []
    const common = node.commonName || node.label
    const scientific = node.scientificName

    if (showCommonNames && common) {
      parts.push(common)
    }
    if (showScientificNames && scientific) {
      if (showCommonNames && common) {
        parts.push(`(${scientific})`)
      } else {
        parts.push(scientific)
      }
    }

    if (!parts.length) {
      return common || scientific || node.label || 'Unknown'
    }
    return parts.join(' ')
  }

  const handleLabelPreferenceChange = (type: 'common' | 'scientific', checked: boolean) => {
    if (type === 'common') {
      if (!checked && !showScientificNames) {
        return
      }
      setShowCommonNames(checked)
    } else {
      if (!checked && !showCommonNames) {
        return
      }
      setShowScientificNames(checked)
    }
  }

  const categoryLabelMap = useMemo(() => {
    const map = new Map<string, string>()
    NETWORK_LEGEND.forEach((entry) => {
      map.set(entry.key, entry.label)
    })
    return map
  }, [])

  const graph = useMemo<{ nodes: NodeDatum[]; links: LinkDatum[] }>(() => {
    const nodesMap = new Map<string, NodeDatum>()
    const linkCounts = new Map<string, LinkDatum>()

    const ensureNode = (
      label: string,
      observation: Observation | undefined,
      isFocal: boolean
    ) => {
      const commonName = getCommonName(observation) || undefined
      const scientificName = getScientificName(observation) || undefined
      const fallbackLabel = commonName || scientificName || label || 'Unknown'
      if (!fallbackLabel) return
      const iconicTaxon = getIconicTaxon(observation)
      const category = getTaxonCategory(iconicTaxon)

      const existing = nodesMap.get(fallbackLabel)
      if (!existing) {
        nodesMap.set(fallbackLabel, {
          id: fallbackLabel,
          label: fallbackLabel,
          commonName,
          scientificName,
          isFocal,
          iconicTaxon,
          category,
        })
        return
      }

      if (isFocal && !existing.isFocal) {
        existing.isFocal = true
      }

      if (!existing.commonName && commonName) {
        existing.commonName = commonName
      }
      if (!existing.scientificName && scientificName) {
        existing.scientificName = scientificName
      }

      if (iconicTaxon !== 'Unidentified' && existing.iconicTaxon === 'Unidentified') {
        existing.iconicTaxon = iconicTaxon
        existing.category = category
      }
    }

    results.forEach((result) => {
      const partner = partnerData[result.id]
      if (!partner) return

      const predatorObservation = type === 'eater' ? partner : result
      const preyObservation = type === 'eater' ? result : partner

      const predatorName = getDisplayName(predatorObservation)
      const preyName = getDisplayName(preyObservation)

      if (!predatorName || !preyName) return

      const source = preyName
      const target = predatorName

      ensureNode(preyName, preyObservation, labelsMatch(preyName, focalName))
      ensureNode(
        predatorName,
        predatorObservation,
        labelsMatch(predatorName, focalName)
      )

      const key = `${source}__${target}`
      const existing = linkCounts.get(key)
      if (existing) {
        existing.count += 1
      } else {
        linkCounts.set(key, {
          source,
          target,
          count: 1,
        })
      }
    })

    return {
      nodes: Array.from(nodesMap.values()),
      links: Array.from(linkCounts.values()),
    }
  }, [partnerData, results, type, focalName])

  useEffect(() => {
    const handleFullscreenChange = () => {
      const target = containerRef.current
      setIsFullScreen(document.fullscreenElement === target)
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  useEffect(() => {
    const svgElement = svgRef.current
    if (!svgElement) return

    const { nodes, links } = graph
    const svg = d3.select(svgElement)
    svg.selectAll('*').remove()
    svgSelectionRef.current = svg

    if (!nodes.length || !links.length) {
      return
    }

    const width = svgElement.clientWidth || 500
    const height = svgElement.clientHeight || 360
    const labelFont = '12px "Inter", system-ui, sans-serif'
    const measureContext = document.createElement('canvas').getContext('2d')
    if (measureContext) {
      measureContext.font = labelFont
    }
    nodes.forEach((node: NodeDatum) => {
      const labelText = formatNodeLabelText(node)
      const measured =
        measureContext?.measureText(labelText).width ||
        labelText.length * 7
      node.labelWidth = measured
    })
    const focalNode = nodes.find((node) => node.isFocal) || nodes[0]
    const centerX = width / 2
    const centerY = height / 2
    if (focalNode) {
      focalNode.x = centerX
      focalNode.y = centerY
    }
    const peripheralNodes = nodes.filter((node) => node !== focalNode)
    const baseRadius = Math.min(width, height) / 3
    peripheralNodes.forEach((node: NodeDatum, index: number) => {
      const angle = (index / Math.max(peripheralNodes.length, 1)) * Math.PI * 2
      const labelRadius = (node.labelWidth ?? 0) * 0.6
      const radius = baseRadius + labelRadius
      node.x = centerX + Math.cos(angle) * radius
      node.y = centerY + Math.sin(angle) * radius
    })

    const defs = svg.append('defs')
    defs
      .append('marker')
      .attr('id', 'mini-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 10)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#475569')

    const zoomLayer = svg.append('g')

    const link = zoomLayer
      .append('g')
      .attr('stroke', '#94a3b8')
      .attr('stroke-opacity', 0.85)
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke-width', (d: LinkDatum) => 1 + d.count)
      .attr('marker-end', 'url(#mini-arrow)')

    const node = zoomLayer
      .append('g')
      .attr('stroke-width', 1.5)
      .selectAll('g')
      .data(nodes)
      .join('g')

    node
      .append('circle')
      .attr('r', (d: NodeDatum) => getNodeRadius(d))
      .attr('fill', (d: NodeDatum) => getCategoryColor(d.iconicTaxon))
      .attr('stroke', (d: NodeDatum) => (d.isFocal ? '#1f2937' : 'transparent'))
      .attr('stroke-width', (d: NodeDatum) => (d.isFocal ? 4 : 0))

    const labels = node
      .append('text')
      .style('font', labelFont)
      .attr('fill', '#0f172a')
      .attr('dy', '0.35em')
      .attr('xml:space', 'preserve')

    const updateLabels = () => {
      labels.text((d: NodeDatum) => formatNodeLabelText(d))
    }
    updateLabels()

    const updateLabelVisibility = (scale: number) => {
      const minScale = 0.12
      const maxScale = 0.35
      const clamped =
        scale <= minScale
          ? 0
          : scale >= maxScale
            ? 1
            : (scale - minScale) / (maxScale - minScale)
      labels.style('opacity', clamped)
    }

    node.append('title').text((d: NodeDatum) => `${d.label}\nGroup: ${categoryLabelMap.get(d.category) || 'Other'}`)

    const simulation = d3
      .forceSimulation(nodes as NodeDatum[])
      .force(
        'link',
        d3
          .forceLink(links as any)
          .id((d: any) => d.id)
          .distance(110)
      )
      .force('charge', d3.forceManyBody().strength(-220))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collide',
        d3
          .forceCollide((d: NodeDatum) => {
            const circleRadius = getNodeRadius(d)
            const labelRadius = (d.labelWidth ?? 0) / 2
            const padding = 14
            return circleRadius + padding + labelRadius
          })
          .iterations(2)
      )
      .alpha(0.6)

    node.call(
      d3
        .drag()
        .on('start', (event: any, d: NodeDatum) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event: any, d: NodeDatum) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event: any, d: NodeDatum) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

    const nodeById = new Map(nodes.map((n) => [n.id, n]))

    const resolveNode = (endpoint: string | NodeDatum): NodeDatum | undefined =>
      typeof endpoint === 'object' ? endpoint : nodeById.get(endpoint)

    const positionedCoords = (d: LinkDatum) => {
      const sourceNode = resolveNode(d.source)
      const targetNode = resolveNode(d.target)
      if (!sourceNode || !targetNode) {
        return {
          x1: 0,
          y1: 0,
          x2: 0,
          y2: 0,
        }
      }
      const sx = sourceNode.x ?? 0
      const sy = sourceNode.y ?? 0
      const tx = targetNode.x ?? 0
      const ty = targetNode.y ?? 0
      const dx = tx - sx
      const dy = ty - sy
      const distance = Math.sqrt(dx * dx + dy * dy) || 1
      const normX = dx / distance
      const normY = dy / distance
      const startRadius = getNodeRadius(sourceNode)
      const endRadius = getNodeRadius(targetNode)
      return {
        x1: sx + normX * startRadius,
        y1: sy + normY * startRadius,
        x2: tx - normX * endRadius,
        y2: ty - normY * endRadius,
      }
    }

    simulation.on('tick', () => {
      link
        .attr('x1', (d: LinkDatum) => positionedCoords(d).x1)
        .attr('y1', (d: LinkDatum) => positionedCoords(d).y1)
        .attr('x2', (d: LinkDatum) => positionedCoords(d).x2)
        .attr('y2', (d: LinkDatum) => positionedCoords(d).y2)

      node.attr('transform', (d: NodeDatum) => `translate(${d.x || 0},${d.y || 0})`)

      labels
        .attr('x', (d: NodeDatum) => {
          const radius = getNodeRadius(d)
          const offset = radius + 10
          return (d.x || 0) >= width / 2 ? offset : -offset
        })
        .attr('text-anchor', (d: NodeDatum) => ((d.x || 0) >= width / 2 ? 'start' : 'end'))
    })

    const zoomBehaviour = d3
      .zoom()
      .scaleExtent([0.005, 8])
      .on('zoom', (event: any) => {
        zoomLayer.attr('transform', event.transform)
        updateLabelVisibility(event.transform.k)
      })

    zoomBehaviourRef.current = zoomBehaviour as any
      svg.call(zoomBehaviour)
    updateLabelVisibility(1)
    updateLabels()

    const focusNode = (nodeDatum: NodeDatum) => {
      if (nodeDatum.x == null || nodeDatum.y == null) return
      const scale = 1.6
      const transform = d3.zoomIdentity
        .translate(width / 2, height / 2)
        .scale(scale)
        .translate(-nodeDatum.x, -nodeDatum.y)

      svg.transition().duration(650).call(zoomBehaviour.transform, transform)
    }

    const resetStyles = () => {
      node
        .select('circle')
        .attr('stroke', (d: NodeDatum) => (d.isFocal ? '#1f2937' : 'transparent'))
        .attr('stroke-width', (d: NodeDatum) => (d.isFocal ? 4 : 0))

      link.attr('stroke', '#94a3b8').attr('stroke-opacity', 0.85)
    }

    resetStyles()

    const searchInput = document.getElementById('searchBox') as
      | HTMLInputElement
      | null
    const searchButton = document.getElementById('searchButton')

    const highlight = (value: string) => {
      const term = value.trim().toLowerCase()
      resetStyles()

      if (!term) return

      const match = nodes.find((n) => {
        const candidates = [n.id, n.label, n.commonName, n.scientificName]
        return candidates.some(
          (entry) => typeof entry === 'string' && entry.toLowerCase() === term
        )
      })
      if (!match) {
        alert(`No match found for "${value}"`)
        return
      }

      node
        .filter((d: NodeDatum) => d.id === match.id)
        .select('circle')
        .attr('stroke', '#0f172a')
        .attr('stroke-width', 5)

      link
        .filter(
          (d: LinkDatum) => {
            const sourceId =
              typeof d.source === 'object' ? d.source.id : d.source
            const targetId =
              typeof d.target === 'object' ? d.target.id : d.target
            return sourceId === match.id || targetId === match.id
          }
        )
        .attr('stroke', '#1f2937')
        .attr('stroke-opacity', 0.9)

      focusNode(match)
    }

    const handleButtonClick = () => {
      if (!searchInput) return
      highlight(searchInput.value)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!searchInput) return
      if (event.key === 'Enter') {
        event.preventDefault()
        highlight(searchInput.value)
      }
      if (event.key === 'Escape') {
        resetStyles()
        searchInput.value = ''
      }
    }

    searchButton?.addEventListener('click', handleButtonClick)
    searchInput?.addEventListener('keydown', handleKeyDown)

    return () => {
      simulation.stop()
      searchButton?.removeEventListener('click', handleButtonClick)
      searchInput?.removeEventListener('keydown', handleKeyDown)
    }
  }, [graph, isFullScreen, showCommonNames, showScientificNames])

  const handleZoom = (factor: number) => {
    if (!svgSelectionRef.current || !zoomBehaviourRef.current) return
    svgSelectionRef.current
      .transition()
      .duration(200)
      .call(zoomBehaviourRef.current.scaleBy, factor)
  }

  const containerClass = isFullScreen
    ? 'flex flex-col lg:flex-row gap-6 w-full h-full bg-white p-4'
    : 'flex flex-col lg:flex-row gap-6'

  const svgWrapperClass = isFullScreen
    ? 'flex-1 w-full border border-slate-200 rounded-lg shadow-sm h-full'
    : 'w-full lg:flex-1 h-80 bg-white border border-slate-200 rounded-lg shadow-sm'

  const handleFullscreenToggle = () => {
    const target = containerRef.current
    if (!target) return
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void target.requestFullscreen()
    }
  }

  if (!graph.nodes.length || !graph.links.length) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No network connections were found for this search.
      </div>
    )
  }

  return (
    <div ref={containerRef} className={containerClass}>
      <div className={`relative ${svgWrapperClass}`}>
        <svg ref={svgRef} className="w-full h-full" role="img" aria-label="Search result network" />
        <div className="absolute top-3 right-3 flex flex-col gap-2">
          <button
            type="button"
            onClick={() => handleZoom(1.2)}
            className="rounded-md bg-slate-800 text-white px-3 py-1 text-sm shadow"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => handleZoom(1 / 1.2)}
            className="rounded-md bg-slate-800 text-white px-3 py-1 text-sm shadow"
          >
            -
          </button>
          <button
            type="button"
            onClick={handleFullscreenToggle}
            className="rounded-md bg-white/90 text-slate-900 px-2 py-1 text-xs shadow"
          >
            {isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'}
          </button>
        </div>
      </div>
      <aside className="w-full lg:w-64">
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-slate-900 mb-2">Name display</h4>
            <div className="flex flex-col gap-2 text-sm text-slate-700">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showCommonNames}
                  onChange={(evt) =>
                    handleLabelPreferenceChange('common', evt.target.checked)
                  }
                />
                Common names
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={showScientificNames}
                  onChange={(evt) =>
                    handleLabelPreferenceChange('scientific', evt.target.checked)
                  }
                />
                Scientific names
              </label>
            </div>
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-900 mb-2">Legend</h4>
            <div className="flex flex-col gap-3 text-sm text-slate-700">
              {NETWORK_LEGEND.map((entry) => (
                <div key={entry.key} className="flex items-center gap-3">
                  <span
                    className="inline-block h-3 w-3 rounded"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span>{entry.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </aside>
    </div>
  )
}
