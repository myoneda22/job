// Thin Amadeus Self-Service API client.
// Docs: https://developers.amadeus.com/self-service

const TOKEN_PATH = "/v1/security/oauth2/token";
const FLIGHT_OFFERS_PATH = "/v2/shopping/flight-offers";
const FLIGHT_DATES_PATH = "/v1/shopping/flight-dates";
const FLIGHT_DESTINATIONS_PATH = "/v1/shopping/flight-destinations";

export interface AmadeusConfig {
  clientId: string;
  clientSecret: string;
  hostname?: string; // "test.api.amadeus.com" or "api.amadeus.com"
}

interface CachedToken {
  token: string;
  expiresAt: number;
}

export class AmadeusClient {
  private readonly clientId: string;
  private readonly clientSecret: string;
  private readonly baseUrl: string;
  private cached: CachedToken | null = null;

  constructor(config: AmadeusConfig) {
    this.clientId = config.clientId;
    this.clientSecret = config.clientSecret;
    const host = config.hostname ?? "test.api.amadeus.com";
    this.baseUrl = `https://${host}`;
  }

  private async getToken(): Promise<string> {
    const now = Date.now();
    if (this.cached && this.cached.expiresAt > now + 30_000) {
      return this.cached.token;
    }
    const res = await fetch(`${this.baseUrl}${TOKEN_PATH}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "client_credentials",
        client_id: this.clientId,
        client_secret: this.clientSecret,
      }),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Amadeus auth failed (${res.status}): ${text}`);
    }
    const data = (await res.json()) as { access_token: string; expires_in: number };
    this.cached = {
      token: data.access_token,
      expiresAt: now + data.expires_in * 1000,
    };
    return data.access_token;
  }

  private async request<T>(path: string, params: Record<string, string | number | undefined>): Promise<T> {
    const token = await this.getToken();
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.amadeus+json" },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Amadeus API error ${res.status} on ${path}: ${text}`);
    }
    return (await res.json()) as T;
  }

  flightOffers(params: {
    originLocationCode: string;
    destinationLocationCode: string;
    departureDate: string;
    returnDate?: string;
    adults: number;
    children?: number;
    infants?: number;
    travelClass?: "ECONOMY" | "PREMIUM_ECONOMY" | "BUSINESS" | "FIRST";
    nonStop?: boolean;
    currencyCode?: string;
    maxPrice?: number;
    max?: number;
  }): Promise<FlightOffersResponse> {
    return this.request<FlightOffersResponse>(FLIGHT_OFFERS_PATH, {
      originLocationCode: params.originLocationCode,
      destinationLocationCode: params.destinationLocationCode,
      departureDate: params.departureDate,
      returnDate: params.returnDate,
      adults: params.adults,
      children: params.children,
      infants: params.infants,
      travelClass: params.travelClass,
      nonStop: params.nonStop ? "true" : undefined,
      currencyCode: params.currencyCode,
      maxPrice: params.maxPrice,
      max: params.max ?? 10,
    });
  }

  cheapestDates(params: {
    origin: string;
    destination: string;
    departureDate?: string;
    oneWay?: boolean;
    duration?: string;
    nonStop?: boolean;
    maxPrice?: number;
    viewBy?: "DATE" | "DURATION" | "WEEK";
  }): Promise<FlightDatesResponse> {
    return this.request<FlightDatesResponse>(FLIGHT_DATES_PATH, {
      origin: params.origin,
      destination: params.destination,
      departureDate: params.departureDate,
      oneWay: params.oneWay ? "true" : undefined,
      duration: params.duration,
      nonStop: params.nonStop ? "true" : undefined,
      maxPrice: params.maxPrice,
      viewBy: params.viewBy,
    });
  }

  inspirationDestinations(params: {
    origin: string;
    departureDate?: string;
    oneWay?: boolean;
    duration?: string;
    nonStop?: boolean;
    maxPrice?: number;
    viewBy?: "COUNTRY" | "DATE" | "DESTINATION" | "DURATION" | "WEEK";
  }): Promise<FlightDestinationsResponse> {
    return this.request<FlightDestinationsResponse>(FLIGHT_DESTINATIONS_PATH, {
      origin: params.origin,
      departureDate: params.departureDate,
      oneWay: params.oneWay ? "true" : undefined,
      duration: params.duration,
      nonStop: params.nonStop ? "true" : undefined,
      maxPrice: params.maxPrice,
      viewBy: params.viewBy,
    });
  }
}

export interface FlightOffersResponse {
  data: FlightOffer[];
  dictionaries?: {
    carriers?: Record<string, string>;
    aircraft?: Record<string, string>;
    locations?: Record<string, { cityCode: string; countryCode: string }>;
  };
}

export interface FlightOffer {
  id: string;
  oneWay: boolean;
  numberOfBookableSeats: number;
  itineraries: Itinerary[];
  price: { currency: string; total: string; grandTotal?: string; base?: string };
  validatingAirlineCodes?: string[];
  travelerPricings?: { fareDetailsBySegment: { cabin: string }[] }[];
}

export interface Itinerary {
  duration: string;
  segments: Segment[];
}

export interface Segment {
  departure: { iataCode: string; terminal?: string; at: string };
  arrival: { iataCode: string; terminal?: string; at: string };
  carrierCode: string;
  number: string;
  duration?: string;
  numberOfStops: number;
}

export interface FlightDatesResponse {
  data: Array<{
    type: string;
    origin: string;
    destination: string;
    departureDate: string;
    returnDate?: string;
    price: { total: string };
    links?: { flightOffers?: string };
  }>;
  meta?: { currency?: string };
}

export interface FlightDestinationsResponse {
  data: Array<{
    type: string;
    origin: string;
    destination: string;
    departureDate: string;
    returnDate?: string;
    price: { total: string };
  }>;
  meta?: { currency?: string };
}
