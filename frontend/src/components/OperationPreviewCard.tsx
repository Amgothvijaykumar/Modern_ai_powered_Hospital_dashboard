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
      <div className="mt-3 border border-emerald-700 border-l-4 bg-emerald-50 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.06em] text-emerald-900">
          <CheckCircle2 className="h-4 w-4" />
          <span>Executed // {confirmResult.operation}</span>
          <Badge variant="success">{confirmResult.affected_rows} rows</Badge>
        </div>
        <p className="mt-1.5 text-xs text-emerald-950">{confirmResult.message}</p>
        {confirmResult.financial_impact && (
          <div className="mt-3 grid grid-cols-3 gap-px border border-emerald-700 bg-emerald-700 text-xs">
            <div className="bg-white p-2 font-mono">
              <div className="text-[10px] uppercase text-neutral-500">Net Before</div>
              <div className="font-bold tabular-nums">₹{confirmResult.financial_impact.total_net_before}</div>
            </div>
            <div className="bg-white p-2 font-mono">
              <div className="text-[10px] uppercase text-neutral-500">Net After</div>
              <div className="font-bold tabular-nums">₹{confirmResult.financial_impact.total_net_after}</div>
            </div>
            <div className="bg-white p-2 font-mono">
              <div className="text-[10px] uppercase text-neutral-500">Total Discount</div>
              <div className="font-bold tabular-nums text-emerald-800">
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
      <div className="mt-3 flex items-center gap-2 border border-neutral-400 bg-[#F4F3EF] p-3 font-mono text-xs text-neutral-700">
        <XCircle className="h-4 w-4 text-neutral-600" />
        <span>Preview cancelled for {preview.operation}. Zero database changes applied.</span>
      </div>
    );
  }

  return (
    <div className="mt-3 border border-[#0A0A0A] border-l-4 border-l-amber-600 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-neutral-200 pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[#0A0A0A]" />
          <span className="font-mono text-[11px] font-bold uppercase tracking-[0.1em] text-[#0A0A0A]">
            Dry-Run Preview Specification
          </span>
          <Badge variant="warning">{preview.operation}</Badge>
        </div>
        <Badge variant="info">Rows: {preview.affected_rows}</Badge>
      </div>

      <p className="mt-2.5 text-xs leading-relaxed text-[#0A0A0A]">{preview.summary}</p>

      {preview.resolved_date_range && (
        <div className="mt-2.5 flex items-center gap-2 border border-[#0A0A0A] bg-[#F4F3EF] px-3 py-2 font-mono text-[11px] text-[#0A0A0A]">
          <Calendar className="h-3.5 w-3.5 shrink-0 text-[#E10600]" />
          <span>
            RESOLVED PERIOD ({preview.resolved_date_range.timezone}):{" "}
            <strong>{preview.resolved_date_range.start_date}</strong> TO{" "}
            <strong>{preview.resolved_date_range.end_date}</strong>
          </span>
        </div>
      )}

      {preview.financial_impact && (
        <div className="mt-2.5 border border-[#0A0A0A]">
          <div className="flex items-center gap-1.5 border-b border-[#0A0A0A] bg-[#F4F3EF] px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.1em] text-[#0A0A0A]">
            <IndianRupee className="h-3 w-3 text-[#E10600]" />
            Financial Impact ({preview.financial_impact.currency || "INR"})
          </div>
          <div className="grid grid-cols-2 gap-px bg-neutral-300 text-xs sm:grid-cols-4">
            <div className="bg-white p-2.5">
              <div className="font-mono text-[10px] uppercase text-neutral-500">Gross Total</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums">
                ₹{preview.financial_impact.total_gross_amount}
              </div>
            </div>
            <div className="bg-white p-2.5">
              <div className="font-mono text-[10px] uppercase text-neutral-500">Net Before</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums">
                ₹{preview.financial_impact.total_net_before}
              </div>
            </div>
            <div className="bg-white p-2.5">
              <div className="font-mono text-[10px] uppercase text-neutral-500">Net After</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums text-[#0A0A0A]">
                ₹{preview.financial_impact.total_net_after}
              </div>
            </div>
            <div className="bg-white p-2.5">
              <div className="font-mono text-[10px] uppercase text-neutral-500">Total Discount</div>
              <div className="mt-0.5 font-mono font-bold tabular-nums text-[#E10600]">
                ₹{preview.financial_impact.total_discount_amount}
              </div>
            </div>
          </div>
        </div>
      )}

      {preview.samples.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-neutral-600">
            Sample Diff ({preview.samples.length} of {preview.affected_rows})
          </div>
          <div className="divide-y divide-neutral-300 border border-neutral-300">
            {preview.samples.map((sample) => (
              <div
                key={sample.id}
                className="grid grid-cols-1 gap-2 bg-white p-2.5 text-xs md:grid-cols-3"
              >
                <div className="font-semibold text-[#0A0A0A]">
                  {sample.item_name || sample.patient_name || sample.full_name || sample.id}
                  {sample.batch_number && (
                    <div className="font-mono text-[10px] text-neutral-500">{sample.batch_number}</div>
                  )}
                </div>
                <div className="font-mono text-[11px] text-neutral-600">
                  <span className="font-bold uppercase text-neutral-500">Before: </span>
                  <code className="break-all">{JSON.stringify(sample.before)}</code>
                </div>
                <div className="font-mono text-[11px] text-[#0A0A0A]">
                  <span className="font-bold uppercase text-[#E10600]">After: </span>
                  <code className="break-all">{JSON.stringify(sample.after)}</code>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {preview.business_rules_note && (
        <p className="mt-2.5 font-mono text-[11px] text-neutral-600">{preview.business_rules_note}</p>
      )}

      {preview.requires_exact_row_count && (
        <div className="mt-3 border border-[#E10600] border-l-4 bg-[#FFF2F2] p-3">
          <div className="flex items-start gap-2 text-xs text-[#0A0A0A]">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#E10600]" />
            <div>
              <strong className="uppercase text-[#E10600]">High-Impact Write (&gt; 50 rows):</strong>{" "}
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
        <div className="mt-2.5 border border-[#E10600] bg-[#FFF2F2] px-3 py-2 text-xs font-medium text-[#E10600]">
          {error}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-neutral-200 pt-3">
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
