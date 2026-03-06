export interface VehicleDecodeResult {
  vehicle: {
    vin: string;
    year: number | null;
    make: string | null;
    model: string | null;
    trim: string | null;
    body_class: string | null;
    fuel_type: string | null;
    drive_type: string | null;
    vehicle_type: string | null;
  };
  valuation: {
    estimated_value: number;
    confidence: "low" | "medium" | "high";
    method: string;
    age_years: number;
    base_value: number;
  } | null;
}

export interface PropertyValuationResult {
  address: string;
  estimated_value: number | null;
  price_low: number | null;
  price_high: number | null;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  lot_size: number | null;
  year_built: number | null;
  property_type: string | null;
  confidence: string;
  source: string;
}

export interface RefreshValuationResult {
  updated: boolean;
  new_value: number;
  vehicle?: VehicleDecodeResult["vehicle"];
  property?: PropertyValuationResult;
}
