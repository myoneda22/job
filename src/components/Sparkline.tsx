'use client'
import { ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts'
import type { HistoryPoint } from '@/types'

interface Props {
  data: HistoryPoint[]
  positive: boolean
}

export function Sparkline({ data, positive }: Props) {
  const color = positive ? '#22c55e' : '#ef4444'
  const gradId = `spark-${positive ? 'up' : 'dn'}`
  return (
    <ResponsiveContainer width="100%" height={56}>
      <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 4 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="close"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradId})`}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ background: '#0f0f0f', border: '1px solid #222', borderRadius: 6, fontSize: 11 }}
          labelStyle={{ display: 'none' }}
          formatter={(v) => {
            const n = Number(v)
            return isNaN(n) ? [String(v), ''] : [`$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`, '']
          }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
