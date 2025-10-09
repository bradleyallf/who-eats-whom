// @ts-nocheck
import { useEffect, useMemo, useRef } from 'react'
import * as d3 from 'd3'
import { Observation, Ofv } from './types'

interface Props {
  results: Observation[]
  partnerData: Record<string, Observation>
  type: Ofv['value']
  focalName: string
}

const COLOR_PALETTE = [
  '#1f77b4',
  '#ff7f0e',
  '#2ca02c',
  '#d62728',
  '#9467bd',
  '#8c564b',
  '#e377c2',
  '#7f7f7f',
  '#bcbd22',
  '#17becf',
  '#393b79',
  '#637939',
  '#8c6d31',
  '#843c39',
  '#7b4173',
  '#3182bd',
  '#e6550d',
  '#31a354',
  '#756bb1',
  '#636363',
]

interface NodeDatum extends d3.SimulationNodeDatum {
  id: string
  label: string
  isFocal: boolean
  iconicTaxon: string
}

interface LinkDatum extends d3.SimulationLinkDatum<NodeDatum> {
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

  const graph = useMemo(() => {
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
      if (!existing) {
        nodesMap.set(label, {
          id: label,
          label,
          isFocal,
          iconicTaxon,
        })
        return
      }

      if (isFocal && !existing.isFocal) {
        existing.isFocal = true
      }

      if (existing.iconicTaxon === 'Unidentified' && iconicTaxon !== 'Unidentified') {
        existing.iconicTaxon = iconicTaxon
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

    const uniqueTaxa = Array.from(
      new Set(nodes.map((node) => node.iconicTaxon))
    ).sort((a, b) => a.localeCompare(b))

    const colorMap = new Map<string, string>()
    uniqueTaxa.forEach((taxon, index) => {
      colorMap.set(taxon, COLOR_PALETTE[index % COLOR_PALETTE.length])
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
      .selectAll<SVGLineElement, LinkDatum>('line')
      .data(links)
      .join('line')
      .attr('stroke-width', (d) => 1 + d.count)
      .attr('marker-end', 'url(#mini-arrow)')

    const node = zoomLayer
      .append('g')
      .attr('stroke-width', 1.5)
      .selectAll<SVGGElement, NodeDatum>('g')
      .data(nodes)
      .join('g')

    node
      .append('circle')
      .attr('r', (d) => (d.isFocal ? 12 : 9))
      .attr('fill', (d) => colorMap.get(d.iconicTaxon) || '#0ea5e9')
      .attr('stroke', (d) => (d.isFocal ? '#f97316' : '#ffffff'))
      .attr('stroke-width', (d) => (d.isFocal ? 3 : 1.5))

    node
      .append('text')
      .attr('x', 14)
      .attr('y', 4)
      .attr('font-size', 12)
      .attr('fill', '#0f172a')
      .text((d) => d.label)

    node.append('title').text((d) => d.label)

    const simulation = d3
      .forceSimulation<NodeDatum>(nodes)
      .force(
        'link',
        d3
          .forceLink<NodeDatum, LinkDatum>(links)
          .id((d: any) => d.id)
          .distance(90)
      )
      .force('charge', d3.forceManyBody().strength(-120))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collide', d3.forceCollide(24))

    node.call(
      d3
        .drag<any, NodeDatum>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as NodeDatum).x || 0)
        .attr('y1', (d) => (d.source as NodeDatum).y || 0)
        .attr('x2', (d) => (d.target as NodeDatum).x || 0)
        .attr('y2', (d) => (d.target as NodeDatum).y || 0)

      node.attr('transform', (d) => `translate(${d.x || 0},${d.y || 0})`)
    })

    const zoomBehaviour = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 5])
      .on('zoom', (event) => {
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
        .attr('stroke', (d) => (d.isFocal ? '#f97316' : '#ffffff'))
        .attr('stroke-width', (d) => (d.isFocal ? 3 : 1.5))

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
        .filter((d) => d.id === match.id)
        .select('circle')
        .attr('stroke', '#f97316')
        .attr('stroke-width', 4)

      link
        .filter(
          (d) =>
            (d.source as NodeDatum).id === match.id ||
            (d.target as NodeDatum).id === match.id
        )
        .attr('stroke', '#f97316')
        .attr('stroke-opacity', 1)

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
    <div className="w-full h-80 bg-white border border-slate-200 rounded-lg shadow-sm">
      <svg ref={svgRef} className="w-full h-full" role="img" aria-label="Search result network" />
    </div>
  )
}
