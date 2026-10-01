export type OrderStatus =
  | "draft"
  | "awaiting_payment"
  | "pending_review"
  | "revision_requested"
  | "approved_queued"
  | "printing"
  | "on_hold"
  | "printed_ready"
  | "rejected"
  | "cancelled"
  | "completed";

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
  source: string;
  reverse_order: boolean;
  collate: boolean;
  free_text_instructions?: string;
}

export interface OrderFile {
  id: number;
  file_name: string;
  file_type: "pdf" | "image";
  content_type: string;
  size: number;
  page_count: number;
  edit_actions: { action: string; [key: string]: unknown }[];
  has_edits: boolean;
  file: string;
  edited_file: string | null;
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
  print_mode: string;
  status: string;
  epson_status: string;
  pages_printed: number;
  error_message: string;
  submitted_at: string | null;
  completed_at: string | null;
}

export interface Order {
  id: number;
  tracking_id: string;
  status: OrderStatus;
  status_display: string;
  payment_type: string;
  client_name: string;
  guest_name: string;
  guest_contact_method: string;
  guest_contact_value: string;
  subtotal: number;
  subtotal_peso: number;
  amount_paid: number;
  amount_paid_peso: number;
  balance_due: number;
  balance_due_peso: number;
  admin_notes: string;
  revision_note: string;
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
  role: "client" | "admin";
  is_shop_admin: boolean;
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

export interface TrackResult {
  tracking_id: string;
  status: OrderStatus;
  status_display: string;
  client_name: string;
  subtotal_peso: number;
  amount_paid_peso: number;
  balance_due_peso: number;
  files: { id: number; file_name: string; page_count: number; file_type: string }[];
  history: { to_status: OrderStatus; to_status_display: string; note: string; created_at: string }[];
  created_at: string;
  updated_at: string;
}
