#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import { AmadeusClient, type FlightOffer, type FlightOffersResponse } from "./amadeus.js";
import { resolveAirport, searchAirports } from "./airports.js";

const SERVER_NAME = "flight-search-mcp";
const SERVER_VERSION = "0.1.0";

function getClient(): AmadeusClient {
  const clientId = process.env.AMADEUS_CLIENT_ID;
  const clientSecret = process.env.AMADEUS_CLIENT_SECRET;
  if (!clientId || !clientSecret) {
    throw new Error(
      "AMADEUS_CLIENT_ID と AMADEUS_CLIENT_SECRET を環境変数に設定してください。https://developers.amadeus.com で無料登録できます。",
    );
  }
  const hostname = process.env.AMADEUS_HOSTNAME ?? "test.api.amadeus.com";
  return new AmadeusClient({ clientId, clientSecret, hostname });
}

function toIata(input: string): string {
  const a = resolveAirport(input);
  if (!a) throw new Error(`空港コードが解決できません: "${input}"。3文字IATAコードか主要都市名で指定してください。`);
  return a.iata;
}

function fmtDuration(iso?: string): string {
  if (!iso) return "";
  const m = iso.match(/^PT(?:(\d+)H)?(?:(\d+)M)?$/);
  if (!m) return iso;
  const h = m[1] ? `${m[1]}h` : "";
  const min = m[2] ? `${m[2]}m` : "";
  return `${h}${min}`.trim() || iso;
}

function summarizeOffer(offer: FlightOffer, dict: FlightOffersResponse["dictionaries"]): string {
  const carriers = dict?.carriers ?? {};
  const lines: string[] = [];
  const price = offer.price.grandTotal ?? offer.price.total;
  lines.push(`💴 ${price} ${offer.price.currency}（残席: ${offer.numberOfBookableSeats}）`);
  offer.itineraries.forEach((itin, i) => {
    const label = offer.itineraries.length === 2 ? (i === 0 ? "往路" : "復路") : "区間";
    lines.push(`  ${label} (${fmtDuration(itin.duration)})`);
    for (const seg of itin.segments) {
      const carrierName = carriers[seg.carrierCode] ?? seg.carrierCode;
      lines.push(
        `    ${seg.departure.at} ${seg.departure.iataCode}${seg.departure.terminal ? `(T${seg.departure.terminal})` : ""}` +
          ` → ${seg.arrival.at} ${seg.arrival.iataCode}${seg.arrival.terminal ? `(T${seg.arrival.terminal})` : ""}` +
          ` / ${carrierName} ${seg.carrierCode}${seg.number}` +
          (seg.numberOfStops > 0 ? ` (経由${seg.numberOfStops}回)` : ""),
      );
    }
  });
  return lines.join("\n");
}

const TOOLS: Tool[] = [
  {
    name: "search_flights",
    description:
      "国内・国際線の航空券を検索し、安い順に提示します。出発地・目的地はIATA 3文字コード（例: HND）または主要都市名（例: 羽田/Tokyo/HND）で指定。",
    inputSchema: {
      type: "object",
      required: ["origin", "destination", "departure_date"],
      properties: {
        origin: { type: "string", description: "出発空港 (IATAコードまたは都市名)" },
        destination: { type: "string", description: "到着空港 (IATAコードまたは都市名)" },
        departure_date: { type: "string", description: "出発日 (YYYY-MM-DD)" },
        return_date: { type: "string", description: "復路日 (YYYY-MM-DD)。省略で片道。" },
        adults: { type: "integer", description: "大人人数 (1-9)", default: 1, minimum: 1, maximum: 9 },
        children: { type: "integer", description: "子供人数 (2-11歳)", default: 0, minimum: 0 },
        infants: { type: "integer", description: "幼児人数 (2歳未満)", default: 0, minimum: 0 },
        travel_class: {
          type: "string",
          enum: ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"],
          description: "座席クラス",
        },
        non_stop: { type: "boolean", description: "直行便のみ", default: false },
        currency: { type: "string", description: "通貨コード (例: JPY, USD)", default: "JPY" },
        max_price: { type: "integer", description: "1名あたり上限価格" },
        max_results: { type: "integer", description: "返却件数 (1-50)", default: 10, minimum: 1, maximum: 50 },
      },
    },
  },
  {
    name: "find_cheapest_dates",
    description:
      "指定した出発地・目的地で、最安となる出発日(と復路日)を検索します。日程が柔軟な旅行プランの相場確認に便利。",
    inputSchema: {
      type: "object",
      required: ["origin", "destination"],
      properties: {
        origin: { type: "string", description: "出発空港 (IATAコードまたは都市名)" },
        destination: { type: "string", description: "到着空港 (IATAコードまたは都市名)" },
        departure_date: { type: "string", description: "出発日または範囲 (YYYY-MM-DD または YYYY-MM-DD,YYYY-MM-DD)" },
        one_way: { type: "boolean", description: "片道のみ", default: false },
        duration: { type: "string", description: "滞在日数 (例: 7) または範囲 (例: 2,8)" },
        non_stop: { type: "boolean", description: "直行便のみ", default: false },
        max_price: { type: "integer", description: "上限価格" },
        view_by: { type: "string", enum: ["DATE", "DURATION", "WEEK"], description: "集計単位" },
      },
    },
  },
  {
    name: "inspire_destinations",
    description:
      "出発地から行ける目的地を、安い順に提案します(インスピレーション検索)。「予算◯円でどこに行ける?」の用途に。",
    inputSchema: {
      type: "object",
      required: ["origin"],
      properties: {
        origin: { type: "string", description: "出発空港 (IATAコードまたは都市名)" },
        departure_date: { type: "string", description: "出発日または範囲" },
        one_way: { type: "boolean", description: "片道", default: false },
        duration: { type: "string", description: "滞在日数または範囲" },
        non_stop: { type: "boolean", description: "直行便のみ", default: false },
        max_price: { type: "integer", description: "上限価格" },
        view_by: {
          type: "string",
          enum: ["COUNTRY", "DATE", "DESTINATION", "DURATION", "WEEK"],
          description: "集計単位",
        },
      },
    },
  },
  {
    name: "lookup_airport",
    description: "都市名・空港名から IATA コードを検索します(例: 「沖縄」→ OKA)。",
    inputSchema: {
      type: "object",
      required: ["query"],
      properties: {
        query: { type: "string", description: "都市名・空港名・IATAコード" },
        limit: { type: "integer", default: 10, minimum: 1, maximum: 50 },
      },
    },
  },
];

const SearchFlightsSchema = z.object({
  origin: z.string(),
  destination: z.string(),
  departure_date: z.string(),
  return_date: z.string().optional(),
  adults: z.number().int().min(1).max(9).default(1),
  children: z.number().int().min(0).default(0),
  infants: z.number().int().min(0).default(0),
  travel_class: z.enum(["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]).optional(),
  non_stop: z.boolean().default(false),
  currency: z.string().default("JPY"),
  max_price: z.number().int().positive().optional(),
  max_results: z.number().int().min(1).max(50).default(10),
});

const FindCheapestDatesSchema = z.object({
  origin: z.string(),
  destination: z.string(),
  departure_date: z.string().optional(),
  one_way: z.boolean().default(false),
  duration: z.string().optional(),
  non_stop: z.boolean().default(false),
  max_price: z.number().int().positive().optional(),
  view_by: z.enum(["DATE", "DURATION", "WEEK"]).optional(),
});

const InspireSchema = z.object({
  origin: z.string(),
  departure_date: z.string().optional(),
  one_way: z.boolean().default(false),
  duration: z.string().optional(),
  non_stop: z.boolean().default(false),
  max_price: z.number().int().positive().optional(),
  view_by: z.enum(["COUNTRY", "DATE", "DESTINATION", "DURATION", "WEEK"]).optional(),
});

const LookupSchema = z.object({
  query: z.string(),
  limit: z.number().int().min(1).max(50).default(10),
});

async function handleSearchFlights(args: unknown): Promise<string> {
  const p = SearchFlightsSchema.parse(args);
  const client = getClient();
  const origin = toIata(p.origin);
  const destination = toIata(p.destination);
  const res = await client.flightOffers({
    originLocationCode: origin,
    destinationLocationCode: destination,
    departureDate: p.departure_date,
    returnDate: p.return_date,
    adults: p.adults,
    children: p.children || undefined,
    infants: p.infants || undefined,
    travelClass: p.travel_class,
    nonStop: p.non_stop,
    currencyCode: p.currency,
    maxPrice: p.max_price,
    max: p.max_results,
  });
  if (!res.data.length) {
    return `候補が見つかりませんでした (${origin} → ${destination}, ${p.departure_date}${p.return_date ? ` / ${p.return_date}` : ""})`;
  }
  const sorted = [...res.data].sort(
    (a, b) => parseFloat(a.price.grandTotal ?? a.price.total) - parseFloat(b.price.grandTotal ?? b.price.total),
  );
  const header = `🛫 ${origin} → ${destination} | ${p.departure_date}${p.return_date ? ` ⇄ ${p.return_date}` : " (片道)"} | 大人${p.adults}${p.children ? ` 子${p.children}` : ""}${p.infants ? ` 幼${p.infants}` : ""}\n${sorted.length}件 (安い順)\n`;
  return header + "\n" + sorted.map((o, i) => `【${i + 1}】\n${summarizeOffer(o, res.dictionaries)}`).join("\n\n");
}

async function handleFindCheapestDates(args: unknown): Promise<string> {
  const p = FindCheapestDatesSchema.parse(args);
  const client = getClient();
  const origin = toIata(p.origin);
  const destination = toIata(p.destination);
  const res = await client.cheapestDates({
    origin,
    destination,
    departureDate: p.departure_date,
    oneWay: p.one_way,
    duration: p.duration,
    nonStop: p.non_stop,
    maxPrice: p.max_price,
    viewBy: p.view_by,
  });
  if (!res.data.length) return `候補なし (${origin} → ${destination})`;
  const currency = res.meta?.currency ?? "";
  const sorted = [...res.data].sort((a, b) => parseFloat(a.price.total) - parseFloat(b.price.total));
  const lines = sorted.map(
    (d, i) =>
      `【${i + 1}】 ${d.departureDate}${d.returnDate ? ` → ${d.returnDate}` : ""} : ${d.price.total} ${currency}`,
  );
  return `📅 ${origin} → ${destination} 最安日 (安い順, ${sorted.length}件)\n\n${lines.join("\n")}`;
}

async function handleInspire(args: unknown): Promise<string> {
  const p = InspireSchema.parse(args);
  const client = getClient();
  const origin = toIata(p.origin);
  const res = await client.inspirationDestinations({
    origin,
    departureDate: p.departure_date,
    oneWay: p.one_way,
    duration: p.duration,
    nonStop: p.non_stop,
    maxPrice: p.max_price,
    viewBy: p.view_by,
  });
  if (!res.data.length) return `候補なし (出発: ${origin})`;
  const currency = res.meta?.currency ?? "";
  const sorted = [...res.data].sort((a, b) => parseFloat(a.price.total) - parseFloat(b.price.total));
  const lines = sorted.map((d, i) => {
    const a = resolveAirport(d.destination);
    const name = a ? `${d.destination} ${a.city}` : d.destination;
    return `【${i + 1}】 ${name} | ${d.departureDate}${d.returnDate ? ` → ${d.returnDate}` : ""} : ${d.price.total} ${currency}`;
  });
  return `✈️ ${origin} 発の安い目的地 (${sorted.length}件)\n\n${lines.join("\n")}`;
}

function handleLookup(args: unknown): string {
  const p = LookupSchema.parse(args);
  const results = searchAirports(p.query, p.limit);
  if (!results.length) return `該当なし: "${p.query}"`;
  return results.map((a) => `${a.iata}  ${a.city} (${a.country})`).join("\n");
}

async function main() {
  const server = new Server(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const { name, arguments: args } = req.params;
    try {
      let text: string;
      switch (name) {
        case "search_flights":
          text = await handleSearchFlights(args);
          break;
        case "find_cheapest_dates":
          text = await handleFindCheapestDates(args);
          break;
        case "inspire_destinations":
          text = await handleInspire(args);
          break;
        case "lookup_airport":
          text = handleLookup(args);
          break;
        default:
          throw new Error(`未知のツール: ${name}`);
      }
      return { content: [{ type: "text", text }] };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { content: [{ type: "text", text: `エラー: ${message}` }], isError: true };
    }
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`${SERVER_NAME} v${SERVER_VERSION} running on stdio`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
