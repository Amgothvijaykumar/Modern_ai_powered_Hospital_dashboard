import React, { useState } from "react";
import { AlertTriangle, Calendar, CheckCircle2, IndianRupee, ShieldCheck, XCircle } from "lucide-react";
import { api } from "@/services/api";
import type { ConfirmResponse, PreviewPayload } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface OperationPreviewCardProps {
  preview: PreviewPayload;
  onResolved?: (outcome: { type: "confirmed" | "cancelled"; result?: ConfirmResponse }) => void;
}

export function OperationPreviewCard({ preview, onResolved }: OperationPreviewCardProps) {
  const [exactCountInput, setExactCountInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<"pending" | "confirmed" | "cancelled">("pending");
  const [confirmResult, setConfirmResult] = useState<ConfirmResponse | null>(null);

  const exactMatches =
    !preview.requires_exact_row_count ||
    exactCountInput.trim() === String(preview.affected_rows);

  const handleConfirm = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const exactRowCount = preview.requires_exact_row_count
        ? Number(exactCountInput.trim())
        : undefined;
      const res = await api.confirmOperation(preview.confirmation_token, exactRowCount);
      setStatus("confirmed");
      setConfirmResult(res);
      onResolved?.({ type: "confirmed", result: res });
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to confirm operation.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await api.cancelOperation(preview.confirmation_token);
      setStatus("cancelled");
      onResolved?.({ type: "cancelled" });
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to cancel preview.");
    } finally {
      setSubmitting(false);
    }
  };

  if (status === "confirmed" && confirmResult) {
    return (
      <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-emerald-900">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <span>Executed · {confirmResult.operation}</span>
          <Badge variant="success">{confirmResult.affected_rows} rows</Badge>
        </div>
        <p className="mt-1.5 text-xs text-emerald-950">{confirmResult.message}</p>
        {confirmResult.financial_impact && (
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-xl bg-white p-2.5 font-mono ring-1 ring-emerald-200">
              <div className="text-[10px] uppercase text-slate-500">Net Before</div>
              <div className="font-bold tabular-nums">₹{confirmResult.financial_impact.total_net_before}</div>
            </div>
            <div className="rounded-xl bg-white p-2.5 font-mono ring-1 ring-emerald-200">
              <div className="text-[10px] uppercase text-slate-500">Net After</div>
              <div className="font-bold tabular-nums">₹{confirmResult.financial_impact.total_net_after}</div>
            </div>
            <div className="rounded-xl bg-white p-2.5 font-mono ring-1 ring-emerald-200">
              <div className="text-[10px] uppercase text-slate-500">Total Discount</div>
              <div className="font-bold tabular-nums text-emerald-700">
                ₹{confirmResult.financial_impact.total_discount_amount}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-100 p-3 text-xs text-slate-600">
        <XCircle className="h-4 w-4 text-slate-500" />
        <span>Preview cancelled for {preview.operation}. Zero database changes applied.</span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-2xl border border-amber-200 bg-white p-4 text-sm shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-amber-600" />
          <span className="text-xs font-bold text-slate-900">
            Dry-Run Preview Specification
          </span>
          <Badge variant="warning">{preview.operation}</Badge>
        </div>
        <Badge variant="info">Rows: {preview.affected_rows}</Badge>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-700">{preview.summary}</p>

      {preview.resolved_date_range && (
        <div className="mt-3 flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-700 ring-1 ring-slate-200">
          <Calendar className="h-3.5 w-3.5 shrink-0 text-indigo-600" />
          <span>
            Period ({preview.resolved_date_range.timezone}):{" "}
            <strong>{preview.resolved_date_range.start_date}</strong> to{" "}
            <strong>{preview.resolved_date_range.end_date}</strong>
          </span>
        </div>
      )}

      {preview.financial_impact && (
        <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
          <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-slate-600">
            <IndianRupee className="h-3 w-3 text-indigo-600" />
            Financial Impact ({preview.financial_impact.currency || "INR"})
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-xl bg-white p-2.5 ring-1 ring-slate-200/80">
              <div className="font-mono text-[10px] uppercase text-slate-400">Gross Total</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums">
                ₹{preview.financial_impact.total_gross_amount}
              </div>
            </div>
            <div className="rounded-xl bg-white p-2.5 ring-1 ring-slate-200/80">
              <div className="font-mono text-[10px] uppercase text-slate-400">Net Before</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums">
                ₹{preview.financial_impact.total_net_before}
              </div>
            </div>
            <div className="rounded-xl bg-white p-2.5 ring-1 ring-slate-200/80">
              <div className="font-mono text-[10px] uppercase text-slate-400">Net After</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums text-slate-900">
                ₹{preview.financial_impact.total_net_after}
              </div>
            </div>
            <div className="rounded-xl bg-white p-2.5 ring-1 ring-slate-200/80">
              <div className="font-mono text-[10px] uppercase text-slate-400">Total Discount</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums text-rose-600">
                ₹{preview.financial_impact.total_discount_amount}
              </div>
            </div>
          </div>
        </div>
      )}

      {preview.samples.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Sample Diff ({preview.samples.length} of {preview.affected_rows})
          </div>
          <div className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200">
            {preview.samples.map((sample) => (
              <div
                key={sample.id}
                className="grid grid-cols-1 gap-2 bg-white p-2.5 text-xs md:grid-cols-3"
              >
                <div className="font-semibold text-slate-900">
                  {sample.item_name || sample.patient_name || sample.full_name || sample.id}
                  {sample.batch_number && (
                    <div className="font-mono text-[10px] text-slate-400">{sample.batch_number}</div>
                  )}
                </div>
                <div className="font-mono text-[11px] text-slate-500">
                  <span className="font-bold uppercase text-slate-400">Before: </span>
                  <code className="break-all">{JSON.stringify(sample.before)}</code>
                </div>
                <div className="font-mono text-[11px] text-slate-900">
                  <span className="font-bold uppercase text-indigo-600">After: </span>
                  <code className="break-all">{JSON.stringify(sample.after)}</code>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {preview.business_rules_note && (
        <p className="mt-2.5 font-mono text-[11px] text-slate-500">{preview.business_rules_note}</p>
      )}

      {preview.requires_exact_row_count && (
        <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 p-3">
          <div className="flex items-start gap-2 text-xs text-slate-900">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <div>
              <strong className="text-rose-700">High-Impact Write (&gt; 50 rows):</strong>{" "}
              Enter exact row count (<strong className="font-mono">{preview.affected_rows}</strong>)
              to unlock execution.
            </div>
          </div>
          <Input
            type="number"
            className="mt-2 max-w-[200px]"
            placeholder={`Type ${preview.affected_rows}`}
            value={exactCountInput}
            onChange={(e) => setExactCountInput(e.target.value)}
          />
        </div>
      )}

      {error && (
        <div className="mt-2.5 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">
          {error}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
        <Button onClick={handleConfirm} disabled={submitting || !exactMatches} size="sm">
          {submitting ? "Executing..." : "Confirm & Execute"}
        </Button>
        <Button onClick={handleCancel} disabled={submitting} variant="outline" size="sm">
          Cancel Preview
        </Button>
      </div>
    </div>
  );
}
