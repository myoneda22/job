'use client'
import { Sparkline } from './Sparkline'
import type { Quote } from '@/types'

const CATEGORY_BADGE: Record<Quote['category'], string> = {
  stock: 'bg-sky-500/10 text-sky-400',
  commodity: 'bg-amber-500/10 text-amber-400',
  crypto: 'bg-violet-500/10 text-violet-400',
}

function fmt(n: number, opts?: Intl.NumberFormatOptions) {
  return n.toLocaleString('en-US', { maximumFractionDigits: 2, ...opts })
}

function fmtLarge(n?: number) {
  if (!n) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  return `$${fmt(n)}`
}

export function PriceCard({ quote }: { quote: Quote }) {
  const up = quote.change >= 0
  const changeColor = up ? 'text-emerald-400' : 'text-red-400'

  return (
    <article className="group relative flex flex-col gap-3 rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 hover:bg-white/[0.06] hover:border-white/10 transition-colors duration-200">
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold tracking-widest text-white/40">
              {quote.symbol}
            </span>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider ${CATEGORY_BADGE[quote.category]}`}>
              {quote.category}
            </span>
          </div>
          <h2 className="mt-0.5 text-sm font-medium text-white/80">{quote.name}</h2>
        </div>
        <div className="text-right">
          <p className="font-mono text-xl font-semibold tabular-nums text-white">
            ${fmt(quote.price)}
          </p>
          <p className={`font-mono text-xs tabular-nums ${changeColor}`}>
            {up ? '+' : ''}{fmt(quote.change)} ({up ? '+' : ''}{fmt(quote.changePercent)}%)
          </p>
        </div>
      </div>

      {/* sparkline */}
      {quote.history.length > 0 && (
        <div className="-mx-1">
          <Sparkline data={quote.history} positive={up} />
        </div>
      )}

      {/* stats row */}
      <div className="grid grid-cols-3 gap-2 border-t border-white/[0.05] pt-3 text-center">
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-widest">High</p>
          <p className="font-mono text-xs text-white/60">${fmt(quote.high)}</p>
        </div>
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-widest">Low</p>
          <p className="font-mono text-xs text-white/60">${fmt(quote.low)}</p>
        </div>
        <div>
          <p className="text-[10px] text-white/30 uppercase tracking-widest">Mkt Cap</p>
          <p className="font-mono text-xs text-white/60">{fmtLarge(quote.marketCap)}</p>
        </div>
      </div>
    </article>
  )
}
