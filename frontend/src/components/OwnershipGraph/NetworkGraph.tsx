import { useRef, useEffect, useCallback } from 'react'
import * as d3 from 'd3'
import type { NetworkNode, NetworkEdge } from '@/types'
import { formatEuroCompact, formatNumber } from '@/utils/format'

interface NetworkGraphProps {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  width?: number
  height?: number
  onNodeClick?: (node: NetworkNode) => void
}

export function NetworkGraph({
  nodes,
  edges,
  width = 800,
  height = 600,
  onNodeClick,
}: NetworkGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const simulationRef = useRef<d3.Simulation<any, any> | null>(null)

  const render = useCallback(() => {
    if (!svgRef.current || nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const g = svg.append('g')

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Build D3 simulation
    const nodeData = nodes.map((n) => ({ ...n, x: width / 2, y: height / 2 }))
    const edgeData = edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
      label: e.label,
    }))

    simulationRef.current = d3
      .forceSimulation(nodeData)
      .force('link', d3.forceLink(edgeData).id((d: any) => d.id).distance(120).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => d.size + 5))

    // Arrow markers
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', '#475569')

    // Edges
    const link = g
      .append('g')
      .selectAll('line')
      .data(edgeData)
      .join('line')
      .attr('stroke', '#334155')
      .attr('stroke-width', (d: any) => Math.min(6, 1 + d.weight * 0.5))
      .attr('stroke-opacity', 0.6)

    // Edge labels
    const edgeLabel = g
      .append('g')
      .selectAll('text')
      .data(edgeData)
      .join('text')
      .attr('font-size', 9)
      .attr('fill', '#64748B')
      .attr('text-anchor', 'middle')
      .text((d: any) => d.weight > 1 ? `${d.weight}` : '')

    // Node groups
    const node = g
      .append('g')
      .selectAll('g')
      .data(nodeData)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<any, any>()
          .on('start', (event, d) => {
            if (!event.active) simulationRef.current?.alphaTarget(0.3).restart()
            d.fx = d.x
            d.fy = d.y
          })
          .on('drag', (event, d) => {
            d.fx = event.x
            d.fy = event.y
          })
          .on('end', (event, d) => {
            if (!event.active) simulationRef.current?.alphaTarget(0)
            d.fx = null
            d.fy = null
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        onNodeClick?.(d as NetworkNode)
      })

    // Node circles
    node
      .append('circle')
      .attr('r', (d: any) => d.size)
      .attr('fill', (d: any) => d.color)
      .attr('fill-opacity', 0.85)
      .attr('stroke', (d: any) => d.is_center ? '#FFFFFF' : d.is_speculator ? '#E63946' : '#1E293B')
      .attr('stroke-width', (d: any) => d.is_center ? 3 : d.is_speculator ? 2 : 1)

    // Speculator warning ring
    node
      .filter((d: any) => d.is_speculator)
      .append('circle')
      .attr('r', (d: any) => d.size + 5)
      .attr('fill', 'none')
      .attr('stroke', '#E63946')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '3 3')
      .attr('stroke-opacity', 0.5)

    // Node labels
    node
      .append('text')
      .attr('dy', (d: any) => d.size + 12)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#94A3B8')
      .attr('pointer-events', 'none')
      .text((d: any) => {
        const label = d.label || 'Propriétaire'
        return label.length > 20 ? label.substring(0, 18) + '…' : label
      })

    // Tooltips via title
    node
      .append('title')
      .text((d: any) => [
        d.label,
        `Type: ${d.type}`,
        `Biens dans la zone: ${d.nb_biens_zone}`,
        d.valeur_portfolio ? `Portfolio: ${formatEuroCompact(d.valeur_portfolio)}` : null,
        d.is_speculator ? '⚠ Comportement spéculatif détecté' : null,
      ].filter(Boolean).join('\n'))

    // Simulation tick
    simulationRef.current.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      edgeLabel
        .attr('x', (d: any) => (d.source.x + d.target.x) / 2)
        .attr('y', (d: any) => (d.source.y + d.target.y) / 2)

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })
  }, [nodes, edges, width, height, onNodeClick])

  useEffect(() => {
    render()
    return () => {
      simulationRef.current?.stop()
    }
  }, [render])

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="w-full h-full"
      style={{ background: 'transparent' }}
    />
  )
}

// Legend for network types
export function NetworkLegend() {
  const items = [
    { color: '#A8DADC', label: 'Particulier' },
    { color: '#F4A261', label: 'SCI' },
    { color: '#457B9D', label: 'Société' },
    { color: '#2A9D8F', label: 'Public' },
    { color: '#E63946', label: 'Spéculateur détecté', dashed: true },
  ]

  return (
    <div className="flex flex-wrap gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <div
            className="w-3 h-3 rounded-full"
            style={{
              background: item.color,
              boxShadow: item.dashed ? `0 0 0 2px ${item.color}40` : undefined,
            }}
          />
          <span className="text-xs text-slate-400">{item.label}</span>
        </div>
      ))}
    </div>
  )
}
