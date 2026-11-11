import React, { useState } from "react";
import {
  AlertCircle,
  Bot,
  HelpCircle,
  Send,
  ShieldAlert,
  Terminal,
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
        "SYSTEM READY. Ask to inspect inventory, calculate INR billing discounts, manage staff permissions, review approvals, or undo your last change. Every write operation executes only after dry-run preview and confirmation.",
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
        <div className="mt-2.5 flex flex-wrap items-center gap-2 border border-amber-700 border-l-4 bg-amber-50 px-3 py-2 text-xs text-amber-950">
          <Badge variant="warning">Pending Approval #{String(approvalReq.short_id)}</Badge>
          <span className="font-mono text-[11px]">
            Escalated to Hospital Admin for review in chat.
          </span>
        </div>
      );
    }

    if (approvals && approvals.length > 0) {
      return (
        <div className="mt-3 divide-y divide-neutral-300 border border-[#0A0A0A] bg-white">
          {approvals.map((req) => (
            <div
              key={String(req.id)}
              className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-xs"
            >
              <div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="info">#{String(req.short_id)}</Badge>
                  <span className="font-bold text-[#0A0A0A]">
                    {String(req.requester_name || "Staff")}
                  </span>
                  <span className="font-mono text-[11px] text-neutral-500">
                    ({String(req.operation)})
                  </span>
                  <Badge variant={req.status === "PENDING" ? "warning" : "outline"}>
                    {String(req.status)}
                  </Badge>
                </div>
                <div className="mt-1 text-neutral-700">{String(req.raw_user_query)}</div>
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
        <div className="mt-3 border border-[#0A0A0A] bg-white">
          <div className="max-h-72 overflow-x-auto overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 border-b border-[#0A0A0A] bg-[#F4F3EF] font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-700">
                <tr>
                  <th className="px-3 py-2">Item Name</th>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">Qty / Min</th>
                  <th className="px-3 py-2">Expiry</th>
                  <th className="px-3 py-2">Batch</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-[#F4F3EF]/60">
                    <td className="px-3 py-2 font-semibold text-[#0A0A0A]">
                      {String(item.item_name)}
                    </td>
                    <td className="px-3 py-2 text-neutral-600">{String(item.category)}</td>
                    <td className="px-3 py-2 font-mono tabular-nums">
                      <span
                        className={
                          item.is_low_stock ? "font-bold text-[#E10600]" : "text-[#0A0A0A]"
                        }
                      >
                        {item.quantity}
                      </span>{" "}
                      / {item.minimum_quantity}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] tabular-nums text-neutral-600">
                      {String(item.expiry_date)}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-neutral-500">
                      {String(item.batch_number)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(data.total_count as number) > items.length && (
            <div className="border-t border-[#0A0A0A] bg-[#F4F3EF] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-neutral-600">
              Showing {items.length} of {data.total_count as number} matching records.
            </div>
          )}
        </div>
      );
    }

    if (bills && bills.length > 0) {
      return (
        <div className="mt-3 overflow-x-auto border border-[#0A0A0A] bg-white">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#0A0A0A] bg-[#F4F3EF] font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-700">
              <tr>
                <th className="px-3 py-2">Patient</th>
                <th className="px-3 py-2">Gross</th>
                <th className="px-3 py-2">Discount</th>
                <th className="px-3 py-2">Net</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-200">
              {bills.slice(0, 10).map((b) => (
                <tr key={b.id} className="hover:bg-[#F4F3EF]/60">
                  <td className="px-3 py-2 font-semibold text-[#0A0A0A]">
                    {String(b.patient_name)}
                  </td>
                  <td className="px-3 py-2 font-mono tabular-nums">₹{String(b.gross_amount)}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-[#E10600]">
                    ₹{String(b.discount_amount)}
                  </td>
                  <td className="px-3 py-2 font-mono font-bold tabular-nums">
                    ₹{String(b.net_amount)}
                  </td>
                  <td className="px-3 py-2">
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
        <div className="mt-3 divide-y divide-neutral-300 border border-[#0A0A0A] bg-white">
          {users.map((u) => (
            <div key={u.id} className="flex items-center justify-between px-3 py-2 text-xs">
              <div>
                <span className="font-bold text-[#0A0A0A]">{String(u.full_name)}</span>{" "}
                <span className="font-mono text-[11px] text-neutral-500">({String(u.email)})</span>
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
    <div className="flex h-[650px] flex-col border border-[#0A0A0A] bg-white">
      <div className="flex items-center justify-between border-b border-[#0A0A0A] bg-[#0A0A0A] px-5 py-3 text-white">
        <div className="flex items-center gap-2.5">
          <Terminal className="h-4 w-4 text-[#E10600]" />
          <h2 className="text-xs font-extrabold uppercase tracking-[0.12em]">
            Conversational Operations Console
          </h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-400">
          Structured Intent // RBAC Enforced
        </span>
      </div>

      <div className="flex flex-wrap gap-1.5 border-b border-[#0A0A0A] bg-[#F4F3EF] px-4 py-2.5">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => sendMessage(prompt)}
            className="border border-neutral-400 bg-white px-2.5 py-1 text-[11px] font-medium text-[#0A0A0A] transition hover:border-[#0A0A0A] hover:bg-[#0A0A0A] hover:text-white"
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
              <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-[#0A0A0A] bg-[#F4F3EF] text-[#0A0A0A]">
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div
              className={`max-w-[85%] px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "border border-[#0A0A0A] bg-[#0A0A0A] text-white"
                  : msg.response?.status === "denied"
                  ? "border border-[#E10600] border-l-4 bg-[#FFF2F2] text-[#0A0A0A]"
                  : msg.response?.status === "clarification_required"
                  ? "border border-amber-700 border-l-4 bg-amber-50 text-[#0A0A0A]"
                  : msg.response?.status === "unsupported" || msg.response?.status === "invalid"
                  ? "border border-neutral-500 border-l-4 bg-[#F4F3EF] text-[#0A0A0A]"
                  : "border border-[#0A0A0A] border-l-4 bg-[#F4F3EF]/60 text-[#0A0A0A]"
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
              <div className="flex h-8 w-8 shrink-0 items-center justify-center border border-[#0A0A0A] bg-[#0A0A0A] text-white">
                <UserIcon className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.08em] text-neutral-600">
            <span className="h-2.5 w-2.5 animate-pulse bg-[#E10600]" />
            <span>Extracting structured intent and enforcing RBAC policy...</span>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
        className="flex items-center gap-2 border-t border-[#0A0A0A] bg-[#F4F3EF] p-3.5"
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
