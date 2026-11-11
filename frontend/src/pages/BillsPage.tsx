import React, { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import type { BillRecord } from "@/types/api";

export function BillsPage() {
  const [bills, setBills] = useState<BillRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [scope, setScope] = useState("hospital");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getBills({
        filter,
        patient_search: search.trim() || undefined,
        limit: 50,
      });
      setBills(res.bills);
      setTotal(res.total_count);
      setScope(res.scope);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load bills.");
    } finally {
      setLoading(false);
    }
  }, [filter, search]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm">
        <div>
          <div className="inline-flex rounded-full bg-emerald-50 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
            03 // Billing &amp; Financial Ledger
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-950">
              Hospital Bills ({total})
            </h1>
            <Badge variant="outline">
              {scope === "own_only" ? "Own Bills Only" : "Hospital Scope"}
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 rounded-2xl border border-slate-200 bg-slate-50 p-1.5">
          {[
            { key: "all", label: "All" },
            { key: "pending", label: "Pending" },
            { key: "partially_paid", label: "Partially Paid" },
            { key: "paid", label: "Paid" },
          ].map((f) => (
            <Button
              key={f.key}
              variant={filter === f.key ? "default" : "ghost"}
              size="sm"
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle>Billing Ledger (INR)</CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              className="pl-9"
              placeholder="Search patient name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <div className="p-6 text-sm font-medium text-rose-600">{error}</div>
          ) : loading ? (
            <div className="p-6 font-mono text-xs text-slate-500">
              Loading bills...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Patient</th>
                    <th className="px-5 py-3">Gross (INR)</th>
                    <th className="px-5 py-3">Discount (INR)</th>
                    <th className="px-5 py-3">Net (INR)</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3">Created (IST)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {bills.map((bill) => (
                    <tr key={bill.id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-3 font-semibold text-slate-900">
                        {bill.patient_name}
                      </td>
                      <td className="px-5 py-3 font-mono tabular-nums">₹{bill.gross_amount}</td>
                      <td className="px-5 py-3 font-mono tabular-nums text-rose-600">
                        ₹{bill.discount_amount}
                      </td>
                      <td className="px-5 py-3 font-mono font-bold tabular-nums">
                        ₹{bill.net_amount}
                      </td>
                      <td className="px-5 py-3">
                        <Badge
                          variant={
                            bill.status === "PAID"
                              ? "success"
                              : bill.status === "CANCELLED"
                              ? "danger"
                              : "warning"
                          }
                        >
                          {bill.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 font-mono text-[11px] tabular-nums text-slate-500">
                        {new Date(bill.created_at_ist).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
