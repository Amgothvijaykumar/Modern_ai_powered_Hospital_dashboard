import axios from "axios";
import type {
  AgentChatResponse,
  AuditLogRecord,
  BillRecord,
  ConfirmResponse,
  HospitalUserRecord,
  InventoryItemRecord,
  PermissionsMeResponse,
  PreviewPayload,
  SessionResponse,
} from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const TOKEN_STORAGE_KEY = "hospital_ai_access_token";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error?.response?.status === 401 && window.location.pathname !== "/login") {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const api = {
  login: async (email: string, password: string): Promise<SessionResponse> => {
    const { data } = await apiClient.post<SessionResponse>("/api/auth/session", {
      email,
      password,
    });
    return data;
  },

  getMyPermissions: async (): Promise<PermissionsMeResponse> => {
    const { data } = await apiClient.get<PermissionsMeResponse>("/api/permissions/me");
    return data;
  },

  getMe: async () => {
    const { data } = await apiClient.get("/api/auth/me");
    return data;
  },

  sendChat: async (message: string): Promise<AgentChatResponse> => {
    const { data } = await apiClient.post<AgentChatResponse>("/api/agent/chat", { message });
    return data;
  },

  createPreview: async (
    operation: string,
    parameters: Record<string, unknown>,
    raw_user_query?: string
  ): Promise<PreviewPayload> => {
    const { data } = await apiClient.post<PreviewPayload>("/api/operations/preview", {
      operation,
      parameters,
      raw_user_query,
    });
    return data;
  },

  confirmOperation: async (
    confirmation_token: string,
    exact_row_count?: number
  ): Promise<ConfirmResponse> => {
    const { data } = await apiClient.post<ConfirmResponse>("/api/operations/confirm", {
      confirmation_token,
      ...(exact_row_count !== undefined ? { exact_row_count } : {}),
    });
    return data;
  },

  cancelOperation: async (confirmation_token: string) => {
    const { data } = await apiClient.post("/api/operations/cancel", { confirmation_token });
    return data;
  },

  getInventory: async (params?: {
    filter?: string;
    category?: string;
    search?: string;
    expiring_days?: number;
    limit?: number;
    offset?: number;
  }) => {
    const { data } = await apiClient.get<{
      total_count: number;
      summary: {
        total_items: number;
        low_stock_count: number;
        out_of_stock_count: number;
        expiring_count: number;
      };
      items: InventoryItemRecord[];
    }>("/api/inventory", { params });
    return data;
  },

  getBills: async (params?: {
    filter?: string;
    period?: string;
    status?: string;
    patient_search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const { data } = await apiClient.get<{
      total_count: number;
      scope: string;
      summary: {
        total_bills: number;
        pending_count: number;
        paid_count: number;
        total_net_amount: string;
      };
      bills: BillRecord[];
    }>("/api/bills", { params });
    return data;
  },

  getUsers: async (params?: { search?: string; role?: string }) => {
    const { data } = await apiClient.get<{
      total_count: number;
      users: HospitalUserRecord[];
    }>("/api/users", { params });
    return data;
  },

  getAuditLogs: async (params?: {
    limit?: number;
    offset?: number;
    operation?: string;
    execution_status?: string;
  }) => {
    const { data } = await apiClient.get<{
      total_count: number;
      items: AuditLogRecord[];
    }>("/api/audit-logs", { params });
    return data;
  },
};

