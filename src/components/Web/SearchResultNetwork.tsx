import { useEffect, useMemo, useRef } from 'react'
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

export const SearchResultNetwork = (props: Props) => {
  const { results, partnerData, type, focalName } = props
  const svgRef = useRef<SVGSVGElement | null>(null)

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
      if (!label) return
      const existing = nodesMap.get(label)
      const iconicTaxon = getIconicTaxon(observation)
      const category = getTaxonCategory(iconicTaxon)
      if (!existing) {
        nodesMap.set(label, {
          id: label,
          label,
          isFocal,
          iconicTaxon,
          category,
        })
        return
      }

      if (isFocal && !existing.isFocal) {
        existing.isFocal = true
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
    const svgElement = svgRef.current
    if (!svgElement) return

    const { nodes, links } = graph
    const svg = d3.select(svgElement)
    svg.selectAll('*').remove()

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
      const measured =
        measureContext?.measureText(node.label).width ||
        node.label.length * 7
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
      .attr('refX', 12)
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
      .attr('r', (d: NodeDatum) => (d.isFocal ? 12 : 9))
      .attr('fill', (d: NodeDatum) => getCategoryColor(d.iconicTaxon))
      .attr('stroke', (d: NodeDatum) => (d.isFocal ? '#1f2937' : '#ffffff'))
      .attr('stroke-width', (d: NodeDatum) => (d.isFocal ? 4 : 1.5))

    const labels = node
      .append('text')
      .style('font', labelFont)
      .attr('fill', '#0f172a')
      .attr('dy', '0.35em')
      .text((d: NodeDatum) => d.label)

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
            const circleRadius = d.isFocal ? 12 : 9
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

    simulation.on('tick', () => {
      link
        .attr('x1', (d: LinkDatum) => (typeof d.source === 'object' ? d.source.x || 0 : 0))
        .attr('y1', (d: LinkDatum) => (typeof d.source === 'object' ? d.source.y || 0 : 0))
        .attr('x2', (d: LinkDatum) => (typeof d.target === 'object' ? d.target.x || 0 : 0))
        .attr('y2', (d: LinkDatum) => (typeof d.target === 'object' ? d.target.y || 0 : 0))

      node.attr('transform', (d: NodeDatum) => `translate(${d.x || 0},${d.y || 0})`)

      labels
        .attr('x', (d: NodeDatum) => {
          const radius = d.isFocal ? 12 : 9
          const offset = radius + 10
          return (d.x || 0) >= width / 2 ? offset : -offset
        })
        .attr('text-anchor', (d: NodeDatum) => ((d.x || 0) >= width / 2 ? 'start' : 'end'))
    })

    const zoomBehaviour = d3
      .zoom()
      .scaleExtent([0.5, 5])
      .on('zoom', (event: any) => {
        zoomLayer.attr('transform', event.transform)
      })

    svg.call(zoomBehaviour)

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
        .attr('stroke', (d: NodeDatum) => (d.isFocal ? '#1f2937' : '#ffffff'))
        .attr('stroke-width', (d: NodeDatum) => (d.isFocal ? 4 : 1.5))

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

      const match = nodes.find((n) => n.id.toLowerCase() === term)
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
  }, [graph])

  if (!graph.nodes.length || !graph.links.length) {
    return (
      <div className="p-4 text-sm text-slate-600">
        No network connections were found for this search.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="w-full h-80 bg-white border border-slate-200 rounded-lg shadow-sm">
        <svg ref={svgRef} className="w-full h-full" role="img" aria-label="Search result network" />
      </div>
      <div className="flex flex-wrap gap-4 text-sm text-slate-700">
        {NETWORK_LEGEND.map((entry) => (
          <div key={entry.key} className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-3 rounded"
              style={{ backgroundColor: entry.color }}
            />
            <span>{entry.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
