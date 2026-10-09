export type OrderStatus =
  | "draft"
  | "awaiting_payment"
  | "pending_review"
  | "revision_requested"
  | "approved_queued"
  | "printing"
  | "on_hold"
  | "printed_ready"
  /** The printer (or its queue) dropped the job — nothing was printed. */
  | "print_cancelled"
  | "rejected"
  | "cancelled"
  | "completed";

export type FileVariant = "original" | "edited" | "final";

export interface PrintSpecification {
  id?: number;
  order_file?: number | null;
  media_size: string;
  media_type: string;
  color_mode: "color" | "mono";
  sides: "none" | "long" | "short";
  print_quality: "draft" | "normal" | "high";
  copies: number;
  borderless: boolean;
  /** Portrait | Landscape — applies to picture files (the shop rotates them). */
  orientation: "portrait" | "landscape";
  source: string;
  reverse_order: boolean;
  collate: boolean;
  free_text_instructions?: string;
}

export interface OrderFileVersion {
  id: number;
  version_number: number;
  version_label: string;
  file_name: string;
  file_type: "pdf" | "image" | "document";
  content_type: string;
  size: number;
  page_count: number;
  file: string;
  created_at: string;
}

export interface OrderFile {
  id: number;
  file_name: string;
  file_type: "pdf" | "image" | "document";
  content_type: string;
  size: number;
  page_count: number;
  edit_actions: { action: string; [key: string]: unknown }[];
  has_edits: boolean;
  file: string;
  edited_file: string | null;
  /** Admin-prepared file (page selection / converted document). */
  final_file: string | null;
  has_final_file: boolean;
  /** True when the shop swapped this upload for a print-ready version. */
  replaced_by_admin: boolean;
  /** True when the shop rendered this document into a printable PDF. */
  rendered_by_admin: boolean;
  /** Customer re-upload counter — 1 = the original upload. */
  current_version: number;
  /** Older uploads, kept when the customer revises a file. */
  versions: OrderFileVersion[];
  /** Pages the admin chose to print; empty means "the whole document". */
  page_selection: number[];
  selected_pages: number[];
  selected_page_count: number;
  page_selection_label: string;
  page_selection_active: boolean;
  /** False for documents the shop must render or convert before printing. */
  print_ready: boolean;
  /** e.g. "595×841 mm sheet, 566×813 mm printable area (5 mm margins)". */
  print_area: string;
  specification?: PrintSpecification;
  uploaded_at: string;
}

export interface OrderHistory {
  id: number;
  from_status: string;
  to_status: OrderStatus;
  to_status_display: string;
  note: string;
  created_at: string;
}

export interface OrderPayment {
  id: number;
  amount: number;
  method: string;
  status: string;
  paid_at: string | null;
  refund_status: string;
  created_at: string;
}

export interface PrintJob {
  id: number;
  epson_job_id: string;
  file_name: string | null;
  order_file: number | null;
  printer_name: string;
  print_mode: string;
  status: string;
  status_display: string;
  epson_status: string;
  pages_printed: number;
  /** Pages sent for this run (empty = every page). */
  pages_snapshot: number[];
  pages_label: string;
  is_reprint: boolean;
  /** True when the printer dropped the job rather than the shop or client. */
  is_printer_cancelled: boolean;
  error_message: string;
  submitted_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Order {
  id: number;
  tracking_id: string;
  status: OrderStatus;
  status_display: string;
  payment_type: string;
  payment_method: "" | "qrph" | "pickup" | "cash";
  client_name: string;
  guest_name: string;
  guest_contact_method: string;
  guest_contact_value: string;
  subtotal: number;
  subtotal_peso: number;
  min_partial_peso: number;
  amount_paid: number;
  amount_paid_peso: number;
  balance_due: number;
  balance_due_peso: number;
  admin_notes: string;
  revision_note: string;
  reprint_count: number;
  files: OrderFile[];
  history: OrderHistory[];
  payments: OrderPayment[];
  print_jobs?: PrintJob[];
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;
}

export interface QuoteLine {
  label: string;
  pages: number;
  copies: number;
  unit_price: number;
  unit_price_peso: number;
  sides: number;
  amount: number;
  amount_peso: number;
}

export interface Quote {
  lines: QuoteLine[];
  subtotal: number;
  subtotal_peso: number;
  min_partial_peso: number;
}

export interface Capabilities {
  printMode: string;
  colorModes: string[];
  resolutions: number[];
  paperSizes: {
    paperSize: string;
    paperTypes: {
      paperType: string;
      borderless: boolean;
      paperSources: string[];
      printQualities: string[];
      doubleSided: boolean;
    }[];
  }[];
}

export interface CurrentUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: "client" | "approver" | "admin";
  is_shop_admin: boolean;
  /** True for the approver role: may work the review queue, not config. */
  is_approver: boolean;
  /** Admins *and* approvers — everyone who may review/print orders. */
  can_review_orders: boolean;
}

/** One shop-side account as the owner sees it in user management. */
export interface StaffUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: "approver" | "admin";
  role_display: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  is_approver: boolean;
  is_shop_admin: boolean;
  date_joined: string;
  last_login: string | null;
}

/** Payload for POST /admin/users/ and PATCH /admin/users/<id>/. */
export interface StaffUserPayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  role: "approver" | "admin";
  password?: string;
  is_active?: boolean;
}

export interface SetupStatus {
  needs_setup: boolean;
}

export interface EpsonStatus {
  mock_mode: boolean;
  client_configured: boolean;
  redirect_uri: string;
  device_connected: boolean;
  refresh_token_source: "database" | "environment" | "none";
}

export interface EpsonAuthUrl {
  authorization_url: string;
  redirect_uri: string;
  state: string;
}

export interface PriceRule {
  id: number;
  media_size: string;
  media_type: string;
  color_mode: string;
  print_quality: string;
  price_per_page: number;
  price_per_page_peso: number;
  effective_date: string;
  is_active: boolean;
}

export type PreviewBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; text: string }
  | { type: "spacer"; text: string }
  | { type: "table"; label?: string; rows: string[][] }
  | { type: "slide"; label: string; title: string; items: string[] };

export interface DocumentPreview {
  kind: "document" | "spreadsheet" | "slides" | "text";
  format: string;
  blocks: PreviewBlock[];
  truncated: boolean;
  block_count: number;
  file_name: string;
  page_count: number;
}

export interface TrackResult {
  id: number;
  tracking_id: string;
  status: OrderStatus;
  status_display: string;
  client_name: string;
  subtotal_peso: number;
  amount_paid_peso: number;
  balance_due_peso: number;
  reprint_count: number;
  files: { id: number; file_name: string; page_count: number; file_type: string;
           /** 1 = the original upload; >1 means the client replaced it. */
           current_version?: number }[];
  history: { to_status: OrderStatus; to_status_display: string; note: string; created_at: string }[];
  created_at: string;
  updated_at: string;
}

export interface ShopPaymentSettings {
  allow_pay_on_pickup: boolean;
  updated_at?: string;
}

/** GET/PUT /pricing/settings/ — the admin-editable global pricing knobs. */
export interface PricingSettings {
  duplex_discount_factor: number;
  min_partial_percent: number;
  fallback_price_per_side: number;
  fallback_price_per_side_peso: number;
  updated_at?: string;
}

/** One entry of POST /orders/estimate/ — a counted upload (never persisted). */
export interface EstimateFile {
  name: string;
  file_type: "pdf" | "image" | "document";
  page_count: number;
  size: number;
  print_ready: boolean;
}

export interface EstimateResponse {
  files: EstimateFile[];
  total_pages: number;
}

/** Paginated shape DefaultRouter + PageNumberPagination returns for lists. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CheckoutResponse {
  method: "qrph" | "pickup";
  detail?: string;
  payment_id?: number;
  amount?: number;
  amount_peso?: number;
  payment_type?: string;
  qr_image_url?: string;
  expires_at?: string | null;
  status?: string;
  mock_mode?: boolean;
  order?: Order;
}

/** One row of the append-only sales ledger (GET /payments/sales/). */
export interface SalesEntry {
  id: number;
  kind: "payment" | "refund";
  /** Centavos; always positive. `kind` carries the sign (+payment / −refund). */
  amount: number;
  amount_peso: number;
  method: string;
  /** Snapshotted tracking id — survives even if the order is later deleted. */
  tracking_id: string;
  /** Null once the linked order has been hard-deleted (SET_NULL). */
  order_id: number | null;
  reason: string;
  occurred_at: string;
}

/** Net totals for a single payment method over the selected range. */
export interface SalesMethodTotal {
  method: string;
  /** Centavos. */
  gross: number;
  refunds: number;
  net: number;
  count: number;
}

/** One day of the daily series (zero-filled for days with no sales). */
export interface SalesDailyPoint {
  date: string;
  /** Centavos. */
  gross: number;
  refunds: number;
  net: number;
}

/** Shop-admin sales overview, read from the append-only SalesEntry ledger. */
export interface SalesDashboard {
  /** Inclusive query window, YYYY-MM-DD. */
  from: string;
  to: string;
  /** Centavos — the raw amount the ledger keeps; divide by 100 for pesos. */
  gross: number;
  refunds: number;
  net: number;
  payment_count: number;
  refund_count: number;
  /** Distinct orders that paid in this window. */
  paid_orders: number;
  methods: SalesMethodTotal[];
  daily: SalesDailyPoint[];
  /** Latest ledger rows for the window. */
  recent: SalesEntry[];
}

export interface CustomerOption {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
}
