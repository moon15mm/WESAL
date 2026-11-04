export type BusinessBrief = {
  id: string; type: string; name: string; trade_name_ar: string; trade_name_en: string | null; slug: string;
  logo_url: string | null; verification_status: string; rating_avg: number; rating_count: number;
  city: { id: number; name: string } | null;
};

export type OrderItem = {
  id: string; offer_id: string; product_id: string; name: string; name_ar: string; name_en: string; sku: string | null;
  unit: "piece" | "carton"; pieces_per_unit: number; quantity: number; list_unit_price: string; unit_price: string;
  discount: string; line_total: string; vat_amount: string; delivered_qty: number | null; returned_qty: number;
};

export type Order = {
  id: string; number: string; status: string; channel: "direct" | "representative";
  retailer: BusinessBrief; supplier: BusinessBrief;
  branch: { id: string; name: string; district: string | null; address_line: string | null; phone: string | null } | null;
  representative: { id: string; display_name: string } | null;
  currency: string; subtotal: string; discount_total: string; delivery_fee: string; vat_rate: string; vat_total: string; total: string;
  version: number; approved_version: number | null; payment_status: string; paid_amount: string; items_count: number;
  notes: string | null; supplier_notes: string | null; expected_delivery_date: string | null; status_reason: string | null;
  submitted_at: string | null; approved_at: string | null; delivered_at: string | null; completed_at: string | null;
  created_at: string; invoice_number: string | null; invoice_url: string | null; actions: string[];
  items?: OrderItem[];
  history?: { from: string | null; to: string; reason: string | null; actor_role: string | null; version: number; at: string }[];
  approvals?: { id: string; version: number; kind: string; decision: string; requested_at: string; opened_at: string | null; decided_at: string | null; method: string | null; comment: string | null; snapshot_hash: string }[];
  pending_approval?: { id: string; version: number; kind: string; snapshot_hash: string } | null;
  offers?: { id: string; version: number; status: string; total: string; delivery_fee: string; valid_until: string | null; notes: string | null; expected_delivery_date: string | null; created_at: string }[];
  delivery?: { status: string; scheduled_date: string | null; dispatched_at: string | null; delivered_at: string | null; driver_name: string | null; driver_phone: string | null; vehicle_plate: string | null; proof_url: string | null; notes: string | null } | null;
  confirmations?: { receiver_name: string | null; has_shortage: boolean; notes: string | null; created_at: string; items: { order_item_id: string; ordered: number; received_qty: number; damaged_qty: number }[] }[];
  collections?: { amount: string; method: string; reference: string | null; collected_at: string; proof_url: string | null }[];
  returns?: { id: string; number: string; status: string; total_value: string }[];
  commission?: { id: string; status: string; amount: string } | null;
};

export type Offer = {
  id: string; supplier_id: string; sku: string | null; unit_price: string; carton_price: string | null; pieces_per_carton: number;
  sell_by_piece: boolean; sell_by_carton: boolean; min_order_qty: number; availability: string; stock_qty: number | null; is_active: boolean;
  product: Product; supplier?: BusinessBrief;
  price?: { piece: { list: string; net: string; promotion_id: string | null }; carton: { list: string; net: string; promotion_id: string | null } };
  delivers_to_you?: boolean; delivery_fee?: string | null;
};

export type Product = {
  id: string; name: string; name_ar: string; name_en: string; description: string | null; description_ar: string | null; description_en: string | null;
  brand: { id: string; name: string } | null; category: { id: number; name: string; slug: string }; barcode: string | null;
  package_size: string | null; pieces_per_carton: number; image_url: string | null; status: string; manufacturer: string | null;
  offers_count?: number; min_unit_price?: string | null;
};
