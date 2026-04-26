// Common airport IATA codes — supports keyword → IATA resolution.
// Includes major Japanese airports plus international hubs.

export interface AirportEntry {
  iata: string;
  city: string;
  country: string;
  aliases: string[];
}

export const AIRPORTS: AirportEntry[] = [
  // 日本（国内）
  { iata: "HND", city: "Tokyo (Haneda)", country: "JP", aliases: ["羽田", "東京", "haneda", "tokyo"] },
  { iata: "NRT", city: "Tokyo (Narita)", country: "JP", aliases: ["成田", "narita"] },
  { iata: "KIX", city: "Osaka (Kansai)", country: "JP", aliases: ["関西", "関空", "大阪", "kansai", "osaka"] },
  { iata: "ITM", city: "Osaka (Itami)", country: "JP", aliases: ["伊丹", "itami"] },
  { iata: "NGO", city: "Nagoya (Chubu)", country: "JP", aliases: ["中部", "セントレア", "名古屋", "centrair", "nagoya"] },
  { iata: "FUK", city: "Fukuoka", country: "JP", aliases: ["福岡", "fukuoka"] },
  { iata: "CTS", city: "Sapporo (New Chitose)", country: "JP", aliases: ["新千歳", "札幌", "chitose", "sapporo"] },
  { iata: "OKA", city: "Okinawa (Naha)", country: "JP", aliases: ["那覇", "沖縄", "naha", "okinawa"] },
  { iata: "SDJ", city: "Sendai", country: "JP", aliases: ["仙台", "sendai"] },
  { iata: "HIJ", city: "Hiroshima", country: "JP", aliases: ["広島", "hiroshima"] },
  { iata: "KOJ", city: "Kagoshima", country: "JP", aliases: ["鹿児島", "kagoshima"] },
  { iata: "KMJ", city: "Kumamoto", country: "JP", aliases: ["熊本", "kumamoto"] },
  { iata: "KMI", city: "Miyazaki", country: "JP", aliases: ["宮崎", "miyazaki"] },
  { iata: "MYJ", city: "Matsuyama", country: "JP", aliases: ["松山", "matsuyama"] },
  { iata: "TAK", city: "Takamatsu", country: "JP", aliases: ["高松", "takamatsu"] },
  { iata: "KCZ", city: "Kochi", country: "JP", aliases: ["高知", "kochi"] },
  { iata: "KKJ", city: "Kitakyushu", country: "JP", aliases: ["北九州", "kitakyushu"] },
  { iata: "OIT", city: "Oita", country: "JP", aliases: ["大分", "oita"] },
  { iata: "NGS", city: "Nagasaki", country: "JP", aliases: ["長崎", "nagasaki"] },
  { iata: "KMQ", city: "Komatsu", country: "JP", aliases: ["小松", "金沢", "komatsu", "kanazawa"] },
  { iata: "TOY", city: "Toyama", country: "JP", aliases: ["富山", "toyama"] },
  { iata: "AOJ", city: "Aomori", country: "JP", aliases: ["青森", "aomori"] },
  { iata: "AKJ", city: "Asahikawa", country: "JP", aliases: ["旭川", "asahikawa"] },
  { iata: "HKD", city: "Hakodate", country: "JP", aliases: ["函館", "hakodate"] },
  { iata: "ISG", city: "Ishigaki", country: "JP", aliases: ["石垣", "ishigaki"] },
  { iata: "MMY", city: "Miyako", country: "JP", aliases: ["宮古島", "miyako"] },

  // アジア
  { iata: "ICN", city: "Seoul (Incheon)", country: "KR", aliases: ["仁川", "ソウル", "incheon", "seoul"] },
  { iata: "GMP", city: "Seoul (Gimpo)", country: "KR", aliases: ["金浦", "gimpo"] },
  { iata: "PUS", city: "Busan", country: "KR", aliases: ["釜山", "busan"] },
  { iata: "TPE", city: "Taipei (Taoyuan)", country: "TW", aliases: ["桃園", "台北", "taoyuan", "taipei"] },
  { iata: "TSA", city: "Taipei (Songshan)", country: "TW", aliases: ["松山(台北)", "songshan"] },
  { iata: "KHH", city: "Kaohsiung", country: "TW", aliases: ["高雄", "kaohsiung"] },
  { iata: "HKG", city: "Hong Kong", country: "HK", aliases: ["香港", "hongkong"] },
  { iata: "SIN", city: "Singapore", country: "SG", aliases: ["シンガポール", "singapore"] },
  { iata: "BKK", city: "Bangkok (Suvarnabhumi)", country: "TH", aliases: ["バンコク", "スワンナプーム", "bangkok"] },
  { iata: "DMK", city: "Bangkok (Don Mueang)", country: "TH", aliases: ["ドンムアン", "donmuang"] },
  { iata: "KUL", city: "Kuala Lumpur", country: "MY", aliases: ["クアラルンプール", "kualalumpur"] },
  { iata: "MNL", city: "Manila", country: "PH", aliases: ["マニラ", "manila"] },
  { iata: "CEB", city: "Cebu", country: "PH", aliases: ["セブ", "cebu"] },
  { iata: "DPS", city: "Bali (Denpasar)", country: "ID", aliases: ["バリ", "デンパサール", "bali", "denpasar"] },
  { iata: "CGK", city: "Jakarta", country: "ID", aliases: ["ジャカルタ", "jakarta"] },
  { iata: "SGN", city: "Ho Chi Minh City", country: "VN", aliases: ["ホーチミン", "hochiminh", "saigon"] },
  { iata: "HAN", city: "Hanoi", country: "VN", aliases: ["ハノイ", "hanoi"] },
  { iata: "PEK", city: "Beijing (Capital)", country: "CN", aliases: ["北京", "首都", "beijing"] },
  { iata: "PKX", city: "Beijing (Daxing)", country: "CN", aliases: ["大興", "daxing"] },
  { iata: "PVG", city: "Shanghai (Pudong)", country: "CN", aliases: ["浦東", "上海", "pudong", "shanghai"] },
  { iata: "SHA", city: "Shanghai (Hongqiao)", country: "CN", aliases: ["虹橋", "hongqiao"] },
  { iata: "CAN", city: "Guangzhou", country: "CN", aliases: ["広州", "guangzhou"] },
  { iata: "DEL", city: "Delhi", country: "IN", aliases: ["デリー", "delhi"] },
  { iata: "BOM", city: "Mumbai", country: "IN", aliases: ["ムンバイ", "mumbai"] },

  // オセアニア
  { iata: "SYD", city: "Sydney", country: "AU", aliases: ["シドニー", "sydney"] },
  { iata: "MEL", city: "Melbourne", country: "AU", aliases: ["メルボルン", "melbourne"] },
  { iata: "BNE", city: "Brisbane", country: "AU", aliases: ["ブリスベン", "brisbane"] },
  { iata: "AKL", city: "Auckland", country: "NZ", aliases: ["オークランド", "auckland"] },
  { iata: "GUM", city: "Guam", country: "GU", aliases: ["グアム", "guam"] },

  // 北米
  { iata: "LAX", city: "Los Angeles", country: "US", aliases: ["ロサンゼルス", "ロス", "losangeles"] },
  { iata: "SFO", city: "San Francisco", country: "US", aliases: ["サンフランシスコ", "sanfrancisco"] },
  { iata: "JFK", city: "New York (JFK)", country: "US", aliases: ["ニューヨーク", "jfk", "newyork"] },
  { iata: "EWR", city: "New York (Newark)", country: "US", aliases: ["ニューアーク", "newark"] },
  { iata: "ORD", city: "Chicago (O'Hare)", country: "US", aliases: ["シカゴ", "chicago", "ohare"] },
  { iata: "SEA", city: "Seattle", country: "US", aliases: ["シアトル", "seattle"] },
  { iata: "HNL", city: "Honolulu", country: "US", aliases: ["ホノルル", "ハワイ", "honolulu", "hawaii"] },
  { iata: "DFW", city: "Dallas/Fort Worth", country: "US", aliases: ["ダラス", "dallas"] },
  { iata: "BOS", city: "Boston", country: "US", aliases: ["ボストン", "boston"] },
  { iata: "IAD", city: "Washington (Dulles)", country: "US", aliases: ["ワシントン", "washington", "dulles"] },
  { iata: "YVR", city: "Vancouver", country: "CA", aliases: ["バンクーバー", "vancouver"] },
  { iata: "YYZ", city: "Toronto", country: "CA", aliases: ["トロント", "toronto"] },

  // 欧州
  { iata: "LHR", city: "London (Heathrow)", country: "GB", aliases: ["ロンドン", "ヒースロー", "london", "heathrow"] },
  { iata: "LGW", city: "London (Gatwick)", country: "GB", aliases: ["ガトウィック", "gatwick"] },
  { iata: "CDG", city: "Paris (CDG)", country: "FR", aliases: ["パリ", "シャルルドゴール", "paris"] },
  { iata: "FRA", city: "Frankfurt", country: "DE", aliases: ["フランクフルト", "frankfurt"] },
  { iata: "MUC", city: "Munich", country: "DE", aliases: ["ミュンヘン", "munich"] },
  { iata: "AMS", city: "Amsterdam", country: "NL", aliases: ["アムステルダム", "amsterdam"] },
  { iata: "FCO", city: "Rome", country: "IT", aliases: ["ローマ", "rome"] },
  { iata: "MAD", city: "Madrid", country: "ES", aliases: ["マドリード", "madrid"] },
  { iata: "BCN", city: "Barcelona", country: "ES", aliases: ["バルセロナ", "barcelona"] },
  { iata: "ZRH", city: "Zurich", country: "CH", aliases: ["チューリッヒ", "zurich"] },
  { iata: "VIE", city: "Vienna", country: "AT", aliases: ["ウィーン", "vienna"] },
  { iata: "IST", city: "Istanbul", country: "TR", aliases: ["イスタンブール", "istanbul"] },
  { iata: "DXB", city: "Dubai", country: "AE", aliases: ["ドバイ", "dubai"] },
  { iata: "DOH", city: "Doha", country: "QA", aliases: ["ドーハ", "doha"] },
];

const IATA_RE = /^[A-Z]{3}$/;

export function resolveAirport(input: string): AirportEntry | null {
  const trimmed = input.trim();
  if (IATA_RE.test(trimmed)) {
    return AIRPORTS.find((a) => a.iata === trimmed) ?? { iata: trimmed, city: trimmed, country: "", aliases: [] };
  }
  const lower = trimmed.toLowerCase();
  return (
    AIRPORTS.find(
      (a) => a.iata.toLowerCase() === lower || a.city.toLowerCase() === lower || a.aliases.some((x) => x.toLowerCase() === lower),
    ) ?? null
  );
}

export function searchAirports(query: string, limit = 10): AirportEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const out: AirportEntry[] = [];
  for (const a of AIRPORTS) {
    if (
      a.iata.toLowerCase().includes(q) ||
      a.city.toLowerCase().includes(q) ||
      a.aliases.some((x) => x.toLowerCase().includes(q))
    ) {
      out.push(a);
      if (out.length >= limit) break;
    }
  }
  return out;
}
