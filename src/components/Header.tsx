'use client'
import { RefreshCw } from 'lucide-react'

interface Props {
  updatedAt?: string
  loading: boolean
  onRefresh: () => void
}

export function Header({ updatedAt, loading, onRefresh }: Props) {
  const time = updatedAt
    ? new Date(updatedAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null

  return (
    <header className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
      <div className="flex items-center gap-3">
        <span className="text-lg font-semibold tracking-tight text-white">Market Monitor</span>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-400">
          Live
        </span>
      </div>
      <div className="flex items-center gap-4">
        {time && (
          <p className="font-mono text-xs text-white/30">
            Updated {time}
          </p>
        )}
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-white/60 hover:bg-white/[0.08] hover:text-white/80 disabled:opacity-40 transition-all duration-150"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>
    </header>
  )
}
