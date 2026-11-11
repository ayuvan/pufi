import React from 'react'

export const SkeletonBox: React.FC<{
  width?: string | number
  height?: string | number
  borderRadius?: string
  style?: React.CSSProperties
}> = ({ width = '100%', height = 20, borderRadius = 'var(--radius-sm)', style }) => {
  return (
    <div
      className="skeleton-shimmer"
      style={{
        width,
        height,
        borderRadius,
        ...style,
      }}
    />
  )
}

export const TableSkeleton: React.FC<{ rows?: number; columns?: number }> = ({
  rows = 5,
  columns = 6,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '16px 0' }}>
      <div style={{ display: 'flex', gap: 16 }}>
        {Array.from({ length: columns }).map((_, c) => (
          <SkeletonBox key={c} height={24} style={{ flex: c === 1 ? 2 : 1 }} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          {Array.from({ length: columns }).map((_, c) => (
            <SkeletonBox key={c} height={36} style={{ flex: c === 1 ? 2 : 1 }} />
          ))}
        </div>
      ))}
    </div>
  )
}
