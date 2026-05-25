'use client'
import { useState } from 'react'
import useSWR from 'swr'
import { Header } from '@/components/Header'
import { FilterBar } from '@/components/FilterBar'
import { PriceCard } from '@/components/PriceCard'
import type { PricesResponse } from '@/types'

type Category = 'all' | 'stock' | 'commodity' | 'crypto'

const fetcher = (url: string) => fetch(url).then((r) => r.json())

export default function HomePage() {
  const [category, setCategory] = useState<Category>('all')

  const { data, isLoading, isValidating, mutate } = useSWR<PricesResponse>(
    '/api/prices',
    fetcher,
    { refreshInterval: 60_000, revalidateOnFocus: false }
  )

  const quotes = (data?.quotes ?? []).filter(
    (q) => category === 'all' || q.category === category
  )

  const gainers = [...quotes].sort((a, b) => b.changePercent - a.changePercent).slice(0, 3)
  const losers  = [...quotes].sort((a, b) => a.changePercent - b.changePercent).slice(0, 3)

  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Header
        updatedAt={data?.updatedAt}
        loading={isLoading || isValidating}
        onRefresh={() => mutate()}
      />

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* summary strip */}
        {data && (
          <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: 'Instruments', value: data.quotes.length },
              { label: 'Advancing', value: data.quotes.filter(q => q.change > 0).length, color: 'text-emerald-400' },
              { label: 'Declining', value: data.quotes.filter(q => q.change < 0).length, color: 'text-red-400' },
              { label: 'Unchanged', value: data.quotes.filter(q => q.change === 0).length },
            ].map((s) => (
              <div key={s.label} className="rounded-lg border border-white/[0.05] bg-white/[0.02] px-4 py-3">
                <p className="text-[10px] uppercase tracking-widest text-white/30">{s.label}</p>
                <p className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${s.color ?? 'text-white'}`}>{s.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* top movers */}
        {quotes.length > 0 && (
          <div className="mb-8 grid gap-4 sm:grid-cols-2">
            <section>
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-emerald-500">Top Gainers</h3>
              <div className="space-y-1">
                {gainers.map((q) => (
                  <div key={q.symbol} className="flex items-center justify-between rounded-lg bg-emerald-500/5 px-3 py-2 text-sm">
                    <span className="font-mono text-xs text-white/60">{q.symbol}</span>
                    <span className="font-mono text-xs font-semibold text-emerald-400">+{q.changePercent.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-red-500">Top Losers</h3>
              <div className="space-y-1">
                {losers.map((q) => (
                  <div key={q.symbol} className="flex items-center justify-between rounded-lg bg-red-500/5 px-3 py-2 text-sm">
                    <span className="font-mono text-xs text-white/60">{q.symbol}</span>
                    <span className="font-mono text-xs font-semibold text-red-400">{q.changePercent.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* filter + grid */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-sm font-medium text-white/50">Watchlist</h2>
          <FilterBar active={category} onChange={setCategory} />
        </div>

        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-48 animate-pulse rounded-xl bg-white/[0.03]" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {quotes.map((q) => (
              <PriceCard key={q.symbol} quote={q} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
