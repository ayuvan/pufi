import React, { useState } from 'react'

// ---------------------------------------------------------------------------
// 1. Area Trend Chart (Interactive SVG)
// ---------------------------------------------------------------------------

export interface TrendDataPoint {
  date: string
  amount: number
  count: number
  label?: string
}

interface AreaTrendChartProps {
  data: TrendDataPoint[]
  height?: number
  currency?: string
}

export const AreaTrendChart: React.FC<AreaTrendChartProps> = ({
  data,
  height = 220,
  currency = 'USD',
}) => {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  if (!data || data.length === 0) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '0.85rem',
        }}
      >
        No historical trend data available.
      </div>
    )
  }

  const padding = { top: 20, right: 24, bottom: 32, left: 24 }
  const chartWidth = 600
  const chartHeight = height

  const innerWidth = chartWidth - padding.left - padding.right
  const innerHeight = chartHeight - padding.top - padding.bottom

  const maxVal = Math.max(...data.map((d) => d.amount), 1)

  // Map data to coordinates
  const points = data.map((d, i) => {
    const x = padding.left + (i / (data.length - 1 || 1)) * innerWidth
    const y = padding.top + innerHeight - (d.amount / maxVal) * innerHeight
    return { x, y, ...d }
  })

  // Create smooth SVG cubic bezier path
  let pathD = `M ${points[0].x} ${points[0].y}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i]
    const p1 = points[i + 1]
    const mx = (p0.x + p1.x) / 2
    pathD += ` C ${mx} ${p0.y}, ${mx} ${p1.y}, ${p1.x} ${p1.y}`
  }

  const fillD = `${pathD} L ${points[points.length - 1].x} ${padding.top + innerHeight} L ${points[0].x} ${padding.top + innerHeight} Z`

  const activePoint = hoverIdx !== null ? points[hoverIdx] : points[points.length - 1]

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {/* Active hover tooltip badge */}
      {activePoint && (
        <div
          style={{
            position: 'absolute',
            top: 6,
            right: 12,
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            boxShadow: 'var(--shadow-sm)',
            borderRadius: 'var(--radius-sm)',
            padding: '4px 10px',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            zIndex: 2,
          }}
        >
          <span style={{ color: 'var(--text-secondary)' }}>{activePoint.date}:</span>
          <strong style={{ color: 'var(--pufi-primary)' }}>
            {new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(
              activePoint.amount
            )}
          </strong>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
            ({activePoint.count} obligations)
          </span>
        </div>
      )}

      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id="pufiAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--pufi-primary)" stopOpacity="0.28" />
            <stop offset="85%" stopColor="var(--pufi-primary)" stopOpacity="0.01" />
            <stop offset="100%" stopColor="var(--pufi-primary)" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Horizontal grid lines */}
        {[0, 0.33, 0.66, 1].map((pct, idx) => {
          const y = padding.top + innerHeight * (1 - pct)
          return (
            <line
              key={idx}
              x1={padding.left}
              y1={y}
              x2={padding.left + innerWidth}
              y2={y}
              stroke="var(--border-subtle)"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
          )
        })}

        {/* Area fill */}
        <path d={fillD} fill="url(#pufiAreaGrad)" />

        {/* Smooth line */}
        <path
          d={pathD}
          fill="none"
          stroke="var(--pufi-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Interactive hover columns & dots */}
        {points.map((p, idx) => {
          const isHovered = hoverIdx === idx
          return (
            <g key={idx} onMouseEnter={() => setHoverIdx(idx)} style={{ cursor: 'pointer' }}>
              {/* Invisible wide hit area */}
              <rect
                x={p.x - innerWidth / (points.length * 2)}
                y={padding.top}
                width={innerWidth / points.length}
                height={innerHeight}
                fill="transparent"
              />

              {/* Crosshair indicator */}
              {isHovered && (
                <line
                  x1={p.x}
                  y1={padding.top}
                  x2={p.x}
                  y2={padding.top + innerHeight}
                  stroke="var(--pufi-primary)"
                  strokeWidth="1"
                  strokeDasharray="2 2"
                />
              )}

              {/* Point circle */}
              <circle
                cx={p.x}
                cy={p.y}
                r={isHovered ? 5.5 : 3.5}
                fill="var(--bg-surface)"
                stroke="var(--pufi-primary)"
                strokeWidth={isHovered ? 3 : 2}
                style={{ transition: 'r 0.15s ease' }}
              />

              {/* X Axis labels */}
              <text
                x={p.x}
                y={padding.top + innerHeight + 18}
                textAnchor="middle"
                fontSize="10"
                fill="var(--text-muted)"
                fontWeight={isHovered ? 700 : 500}
              >
                {p.date}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 2. Status Donut Breakdown Chart
// ---------------------------------------------------------------------------

export interface DonutSegment {
  label: string
  count: number
  color: string
}

interface StatusDonutChartProps {
  segments: DonutSegment[]
  totalLabel?: string
  size?: number
}

export const StatusDonutChart: React.FC<StatusDonutChartProps> = ({
  segments,
  totalLabel = 'Total Records',
  size = 180,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const total = segments.reduce((sum, s) => sum + s.count, 0)

  const radius = 64
  const strokeWidth = 18
  const center = size / 2
  const circumference = 2 * Math.PI * radius

  let cumulativeAngle = -90

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
      <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Background track circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--bg-subtle)"
            strokeWidth={strokeWidth}
          />

          {/* Slices */}
          {total > 0 &&
            segments.map((seg, idx) => {
              const fraction = seg.count / total
              const strokeDasharray = `${fraction * circumference} ${circumference}`
              const transform = `rotate(${cumulativeAngle} ${center} ${center})`
              cumulativeAngle += fraction * 360
              const isHovered = hoveredIdx === idx

              return (
                <circle
                  key={seg.label}
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={strokeDasharray}
                  transform={transform}
                  strokeLinecap="round"
                  style={{
                    cursor: 'pointer',
                    transition: 'stroke-width 0.2s ease, opacity 0.2s ease',
                    opacity: hoveredIdx !== null && !isHovered ? 0.45 : 1,
                  }}
                  onMouseEnter={() => setHoverIdxSafe(idx)}
                  onMouseLeave={() => setHoverIdxSafe(null)}
                />
              )
            })}
        </svg>

        {/* Center label */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
          }}
        >
          <span
            className="num-tabular"
            style={{
              fontSize: '1.45rem',
              fontWeight: 800,
              color: 'var(--text-primary)',
              lineHeight: 1,
            }}
          >
            {hoveredIdx !== null ? segments[hoveredIdx].count : total}
          </span>
          <span
            style={{
              fontSize: '0.68rem',
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              fontWeight: 600,
              marginTop: 4,
            }}
          >
            {hoveredIdx !== null ? segments[hoveredIdx].label : totalLabel}
          </span>
        </div>
      </div>

      {/* Legend list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minWidth: 160 }}>
        {segments.map((seg, idx) => {
          const pct = total > 0 ? ((seg.count / total) * 100).toFixed(0) : '0'
          const isHovered = hoveredIdx === idx

          return (
            <div
              key={seg.label}
              onMouseEnter={() => setHoverIdxSafe(idx)}
              onMouseLeave={() => setHoverIdxSafe(null)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                background: isHovered ? 'var(--bg-subtle)' : 'transparent',
                cursor: 'pointer',
                transition: 'background 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: seg.color,
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  {seg.label}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                  {seg.count}
                </strong>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  ({pct}%)
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )

  function setHoverIdxSafe(idx: number | null) {
    setHoveredIdx(idx)
  }
}

// ---------------------------------------------------------------------------
// 3. Comparative Route Bar Chart
// ---------------------------------------------------------------------------

export interface RouteBarItem {
  name: string
  cost: number
  fee: number
  speedHours: number
  eligible: boolean
  isRecommended: boolean
}

export const ComparativeRouteBarChart: React.FC<{ items: RouteBarItem[]; currency?: string }> = ({
  items,
  currency = 'USD',
}) => {
  const maxCost = Math.max(...items.filter((i) => i.eligible).map((i) => i.cost), 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {items.map((item) => {
        const costPct = item.eligible ? Math.min(100, (item.cost / maxCost) * 100) : 0

        return (
          <div
            key={item.name}
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
              opacity: item.eligible ? 1 : 0.45,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {item.name}
                </span>
                {item.isRecommended && (
                  <span
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      background: 'var(--pufi-primary)',
                      color: '#FFF',
                      padding: '1px 6px',
                      borderRadius: 'var(--radius-pill)',
                    }}
                  >
                    AI PICK
                  </span>
                )}
                {!item.eligible && (
                  <span
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      background: 'var(--pufi-danger-bg)',
                      color: 'var(--pufi-danger-text)',
                      padding: '1px 6px',
                      borderRadius: 'var(--radius-pill)',
                    }}
                  >
                    EXCLUDED
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Est. ~{item.speedHours}h
                </span>
                <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  {item.eligible
                    ? new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(item.cost)
                    : 'N/A'}
                </strong>
              </div>
            </div>

            {/* Bar Track */}
            <div
              style={{
                height: 10,
                borderRadius: 'var(--radius-pill)',
                background: 'var(--bg-subtle)',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: `${costPct}%`,
                  height: '100%',
                  borderRadius: 'var(--radius-pill)',
                  background: item.isRecommended
                    ? 'linear-gradient(90deg, #1677FF, #42A5FF)'
                    : item.eligible
                    ? 'var(--text-secondary)'
                    : 'var(--pufi-danger)',
                  transition: 'width 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
