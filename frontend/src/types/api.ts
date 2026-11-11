export interface UserSummary {
  id: string;
  hospital_id: string;
  hospital_name: string;
  full_name: string;
  email: string;
  roles: string[];
  is_active: boolean;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  user: UserSummary;
}

export interface EffectivePermissionDetail {
  permission_key: string;
  allowed: boolean;
  source: string;
  constraints: Record<string, unknown>;
}

export interface PermissionsMeResponse {
  user_id: string;
  hospital_id: string;
  hospital_name: string;
  roles: string[];
  permissions: Record<string, EffectivePermissionDetail>;
}

export interface PreviewSample {
  id: string;
  item_name?: string;
  batch_number?: string;
  patient_name?: string;
  status?: string;
  full_name?: string;
  email?: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface PreviewPayload {
  confirmation_token: string;
  operation: string;
  summary: string;
  affected_rows: number;
  requires_exact_row_count: boolean;
  samples: PreviewSample[];
  financial_impact?: Record<string, string> | null;
  resolved_date_range?: {
    period: string;
    start_date: string;
    end_date: string;
    timezone: string;
  } | null;
  business_rules_note?: string | null;
  expires_at: string;
}

export interface AgentChatResponse {
  status:
    | "completed"
    | "preview_required"
    | "clarification_required"
    | "denied"
    | "unsupported"
    | "invalid"
    | "not_found";
  message: string;
  intent?: string | null;
  operation?: string | null;
  extractor_source?: string | null;
  data?: Record<string, unknown> | null;
  preview?: PreviewPayload | null;
  clarification_question?: string | null;
  clarification_options?: string[] | null;
  audit_id?: string | null;
}

export interface ConfirmResponse {
  status: string;
  operation: string;
  message: string;
  affected_rows: number;
  financial_impact?: Record<string, string> | null;
  before_data: Record<string, unknown>;
  after_data: Record<string, unknown>;
}

export interface InventoryItemRecord {
  id: string;
  item_name: string;
  category: string;
  quantity: number;
  minimum_quantity: number;
  unit_price: string;
  expiry_date: string;
  batch_number: string;
  is_low_stock: boolean;
  version: number;
}

export interface BillRecord {
  id: string;
  patient_name: string;
  gross_amount: string;
  discount_amount: string;
  net_amount: string;
  status: string;
  created_by_user_id: string;
  created_at_ist: string;
  version: number;
}

export interface HospitalUserRecord {
  id: string;
  full_name: string;
  email: string;
  is_active: boolean;
  roles: string[];
  overrides: { permission_key: string; effect: string }[];
  effective_permissions?: Record<
    string,
    { allowed: boolean; source: string; constraints: Record<string, unknown> }
  >;
}

export interface AuditLogRecord {
  id: string;
  hospital_id: string | null;
  user_id: string | null;
  raw_user_query: string;
  parsed_intent: Record<string, unknown> | null;
  operation: string | null;
  authorization_result: string;
  decision_reason: string;
  affected_rows: number | null;
  execution_status: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  created_at: string;
}

