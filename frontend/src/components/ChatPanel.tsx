import React, { useState } from "react";
import {
  AlertCircle,
  Bot,
  HelpCircle,
  Send,
  ShieldAlert,
  Sparkles,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/services/api";
import type { AgentChatResponse } from "@/types/api";
import { OperationPreviewCard } from "@/components/OperationPreviewCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: AgentChatResponse;
}

const SUGGESTED_PROMPTS = [
  "Show medicines with low stock.",
  "Which medicines are expiring in the next 30 days?",
  "Increase quantity by 10 for all Antibiotics.",
  "Apply a 20% discount to last month's bills.",
  "Last month bills ki 20% discount ivvu",
  "Show pending approval requests.",
  "Undo my last change.",
  "Remove inventory edit access from Ravi.",
  "Give Ravi access.",
];

export function ChatPanel({ onDataChanged }: { onDataChanged?: () => void }) {
  const { user } = useAuth();
  const isAdmin = Boolean(user?.roles?.includes("Admin"));
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Workspace Copilot ready. Ask to inspect inventory, calculate INR billing discounts, manage staff permissions, review approvals, or undo your last change. Every write operation requires a dry-run preview and explicit confirmation.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async (text?: string) => {
    const query = (text ?? input).trim();
    if (!query || loading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: query,
    };
    setMessages((prev) => [...prev, userMsg]);
    if (!text) setInput("");
    setLoading(true);

    try {
      const resp = await api.sendChat(query);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: resp.message,
          response: resp,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content:
            err?.response?.data?.detail ||
            "An unexpected error occurred while processing your request.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const renderStructuredData = (resp: AgentChatResponse) => {
    const data = resp.data;
    if (!data) return null;

    const items = Array.isArray(data.items) ? (data.items as Record<string, any>[]) : null;
    const bills = Array.isArray(data.bills) ? (data.bills as Record<string, any>[]) : null;
    const users = Array.isArray(data.users) ? (data.users as Record<string, any>[]) : null;
    const approvals = Array.isArray(data.approvals)
      ? (data.approvals as Record<string, any>[])
      : null;
    const approvalReq =
      data.approval_request && typeof data.approval_request === "object"
        ? (data.approval_request as Record<string, any>)
        : null;

    if (approvalReq) {
      return (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-950">
          <Badge variant="warning">Pending Approval #{String(approvalReq.short_id)}</Badge>
          <span className="text-xs font-medium">
            Escalated to Hospital Admin for review in chat.
          </span>
        </div>
      );
    }

    if (approvals && approvals.length > 0) {
      return (
        <div className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {approvals.map((req) => (
            <div
              key={String(req.id)}
              className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs"
            >
              <div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="info">#{String(req.short_id)}</Badge>
                  <span className="font-bold text-slate-900">
                    {String(req.requester_name || "Staff")}
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">
                    ({String(req.operation)})
                  </span>
                  <Badge variant={req.status === "PENDING" ? "warning" : "outline"}>
                    {String(req.status)}
                  </Badge>
                </div>
                <div className="mt-1 text-slate-600">{String(req.raw_user_query)}</div>
              </div>
              {req.status === "PENDING" && isAdmin && (
                <div className="flex gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => sendMessage(`Approve request #${String(req.short_id)}`)}
                  >
                    Approve
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => sendMessage(`Reject request #${String(req.short_id)}`)}
                  >
                    Reject
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      );
    }

    if (items && items.length > 0) {
      return (
        <div className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="max-h-72 overflow-x-auto overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 border-b border-slate-200 bg-slate-50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-3.5 py-2.5">Item Name</th>
                  <th className="px-3.5 py-2.5">Category</th>
                  <th className="px-3.5 py-2.5">Qty / Min</th>
                  <th className="px-3.5 py-2.5">Expiry</th>
                  <th className="px-3.5 py-2.5">Batch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80">
                    <td className="px-3.5 py-2 font-semibold text-slate-900">
                      {String(item.item_name)}
                    </td>
                    <td className="px-3.5 py-2 text-slate-600">{String(item.category)}</td>
                    <td className="px-3.5 py-2 font-mono tabular-nums">
                      <span
                        className={
                          item.is_low_stock ? "font-bold text-rose-600" : "text-slate-900"
                        }
                      >
                        {item.quantity}
                      </span>{" "}
                      / {item.minimum_quantity}
                    </td>
                    <td className="px-3.5 py-2 font-mono text-[11px] tabular-nums text-slate-600">
                      {String(item.expiry_date)}
                    </td>
                    <td className="px-3.5 py-2 font-mono text-[11px] text-slate-500">
                      {String(item.batch_number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data.total_count as number) > items.length && (
            <div className="border-t border-slate-100 bg-slate-50 px-3.5 py-2 font-mono text-[10px] uppercase tracking-wider text-slate-500">
              Showing {items.length} of {data.total_count as number} matching records.
            </div>
          )}
        </div>
      );
    }

    if (bills && bills.length > 0) {
      return (
        <div className="mt-3 overflow-x-auto overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 bg-slate-50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3.5 py-2.5">Patient</th>
                <th className="px-3.5 py-2.5">Gross</th>
                <th className="px-3.5 py-2.5">Discount</th>
                <th className="px-3.5 py-2.5">Net</th>
                <th className="px-3.5 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {bills.slice(0, 10).map((b) => (
                <tr key={b.id} className="hover:bg-slate-50/80">
                  <td className="px-3.5 py-2 font-semibold text-slate-900">
                    {String(b.patient_name)}
                  </td>
                  <td className="px-3.5 py-2 font-mono tabular-nums">₹{String(b.gross_amount)}</td>
                  <td className="px-3.5 py-2 font-mono tabular-nums text-rose-600">
                    ₹{String(b.discount_amount)}
                  </td>
                  <td className="px-3.5 py-2 font-mono font-bold tabular-nums">
                    ₹{String(b.net_amount)}
                  </td>
                  <td className="px-3.5 py-2">
                    <Badge variant={b.status === "PAID" ? "success" : "warning"}>
                      {String(b.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (users && users.length > 0) {
      return (
        <div className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-4 py-2.5 text-xs">
              <div>
                <span className="font-bold text-slate-900">{String(u.full_name)}</span>{" "}
                <span className="font-mono text-[11px] text-slate-500">({String(u.email)})</span>
              </div>
              <div className="flex gap-1">
                {(u.roles as string[]).map((r) => (
                  <Badge key={r} variant="info">
                    {r}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="flex h-[660px] flex-col overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 bg-slate-950 px-6 py-4 text-white">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </div>
          <h2 className="text-sm font-bold tracking-tight">
            Conversational Operations Copilot
          </h2>
        </div>
        <span className="rounded-full bg-white/10 px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-slate-300">
          Structured Intent · RBAC Enforced
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 border-b border-slate-100 bg-slate-50/80 px-5 py-3">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => sendMessage(prompt)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto bg-white p-5">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-slate-950 text-white"
                  : msg.response?.status === "denied"
                  ? "border border-rose-200 bg-rose-50/80 text-slate-900"
                  : msg.response?.status === "clarification_required"
                  ? "border border-amber-200 bg-amber-50/80 text-slate-900"
                  : msg.response?.status === "unsupported" || msg.response?.status === "invalid"
                  ? "border border-slate-200 bg-slate-100 text-slate-900"
                  : "border border-slate-200/80 bg-slate-50/80 text-slate-900"
              }`}
            >
              {msg.response && (
                <div className="mb-2 flex flex-wrap items-center gap-1.5">
                  {msg.response.status === "denied" && (
                    <Badge variant="danger" className="gap-1">
                      <ShieldAlert className="h-3 w-3" /> Denied
                    </Badge>
                  )}
                  {msg.response.status === "clarification_required" && (
                    <Badge variant="warning" className="gap-1">
                      <HelpCircle className="h-3 w-3" /> Clarification Required
                    </Badge>
                  )}
                  {msg.response.status === "unsupported" && (
                    <Badge variant="outline" className="gap-1">
                      <AlertCircle className="h-3 w-3" /> Unsupported
                    </Badge>
                  )}
                  {msg.response.operation && (
                    <Badge variant="outline">{msg.response.operation}</Badge>
                  )}
                </div>
              )}

              <p className="whitespace-pre-wrap text-[13px] leading-relaxed">{msg.content}</p>

              {msg.response && renderStructuredData(msg.response)}

              {msg.response?.preview && (
                <OperationPreviewCard
                  preview={msg.response.preview}
                  onResolved={(outcome) => {
                    if (outcome.type === "confirmed") {
                      onDataChanged?.();
                    }
                  }}
                />
              )}
            </div>
            {msg.role === "user" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-slate-950 text-white">
                <UserIcon className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-indigo-600" />
            <span>Extracting structured intent and enforcing RBAC policy...</span>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
        className="flex items-center gap-2 border-t border-slate-100 bg-slate-50/80 p-4"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about low-stock medicines, expiring batches, bill discounts, approvals, or undo..."
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !input.trim()}>
          <Send className="h-3.5 w-3.5" />
          Send
        </Button>
      </form>
    </div>
  );
}
