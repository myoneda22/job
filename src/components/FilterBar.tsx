'use client'

type Category = 'all' | 'stock' | 'commodity' | 'crypto'

interface Props {
  active: Category
  onChange: (c: Category) => void
}

const FILTERS: { label: string; value: Category }[] = [
  { label: 'All', value: 'all' },
  { label: 'Stocks', value: 'stock' },
  { label: 'Commodities', value: 'commodity' },
  { label: 'Crypto', value: 'crypto' },
]

export function FilterBar({ active, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {FILTERS.map((f) => (
        <button
          key={f.value}
          onClick={() => onChange(f.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-150 ${
            active === f.value
              ? 'bg-white/10 text-white'
              : 'text-white/40 hover:text-white/70 hover:bg-white/[0.04]'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}
