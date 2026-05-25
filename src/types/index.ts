export interface Quote {
  symbol: string
  name: string
  price: number
  change: number
  changePercent: number
  high: number
  low: number
  volume: number
  marketCap?: number
  category: 'stock' | 'commodity' | 'crypto'
  history: HistoryPoint[]
}

export interface HistoryPoint {
  date: string
  close: number
}

export interface PricesResponse {
  quotes: Quote[]
  updatedAt: string
}
