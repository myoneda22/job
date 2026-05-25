export interface TickerMeta {
  symbol: string
  name: string
  category: 'stock' | 'commodity' | 'crypto'
}

export const TICKERS: TickerMeta[] = [
  { symbol: 'AAPL',    name: 'Apple',     category: 'stock' },
  { symbol: 'MSFT',    name: 'Microsoft', category: 'stock' },
  { symbol: 'NVDA',    name: 'NVIDIA',    category: 'stock' },
  { symbol: 'GOOGL',   name: 'Alphabet',  category: 'stock' },
  { symbol: 'TSLA',    name: 'Tesla',     category: 'stock' },
  { symbol: 'AMZN',    name: 'Amazon',    category: 'stock' },
  { symbol: 'GC=F',    name: 'Gold',      category: 'commodity' },
  { symbol: 'SI=F',    name: 'Silver',    category: 'commodity' },
  { symbol: 'CL=F',    name: 'Crude Oil', category: 'commodity' },
  { symbol: 'BTC-USD', name: 'Bitcoin',   category: 'crypto' },
  { symbol: 'ETH-USD', name: 'Ethereum',  category: 'crypto' },
]
