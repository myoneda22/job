import { NextResponse } from 'next/server'
import YahooFinance from 'yahoo-finance2'
import { TICKERS } from '@/lib/tickers'
import type { Quote, PricesResponse, HistoryPoint } from '@/types'

export const revalidate = 0

const yf = new YahooFinance()

export async function GET() {
  try {
    const results = await Promise.allSettled(
      TICKERS.map(async (t) => {
        const [quote, historical] = await Promise.all([
          yf.quote(t.symbol),
          yf.historical(t.symbol, {
            period1: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            period2: new Date().toISOString().split('T')[0],
            interval: '1d',
          }),
        ])

        const history: HistoryPoint[] = historical
          .filter((h) => h.close != null)
          .map((h) => ({
            date: (h.date as Date).toISOString().split('T')[0],
            close: h.close as number,
          }))

        const out: Quote = {
          symbol: t.symbol,
          name: t.name,
          category: t.category,
          price: quote.regularMarketPrice ?? 0,
          change: quote.regularMarketChange ?? 0,
          changePercent: quote.regularMarketChangePercent ?? 0,
          high: quote.regularMarketDayHigh ?? 0,
          low: quote.regularMarketDayLow ?? 0,
          volume: quote.regularMarketVolume ?? 0,
          marketCap: quote.marketCap,
          history,
        }
        return out
      })
    )

    const quotes: Quote[] = results
      .filter((r): r is PromiseFulfilledResult<Quote> => r.status === 'fulfilled')
      .map((r) => r.value)

    const body: PricesResponse = { quotes, updatedAt: new Date().toISOString() }
    return NextResponse.json(body)
  } catch (err) {
    console.error('prices route error', err)
    return NextResponse.json({ error: 'Failed to fetch prices' }, { status: 500 })
  }
}
