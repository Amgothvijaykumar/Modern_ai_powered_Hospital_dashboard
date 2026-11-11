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
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b-2 border-[#0A0A0A] pb-4">
        <div>
          <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#E10600]">
            03 // Billing &amp; Financial Ledger
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-extrabold uppercase tracking-tight text-[#0A0A0A]">
              Hospital Bills ({total})
            </h1>
            <Badge variant="outline">
              {scope === "own_only" ? "Own Bills Only" : "Hospital Scope"}
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap border border-[#0A0A0A] bg-white">
          {[
            { key: "all", label: "All" },
            { key: "pending", label: "Pending" },
            { key: "partially_paid", label: "Partially Paid" },
            { key: "paid", label: "Paid" },
          ].map((f, idx) => (
            <Button
              key={f.key}
              variant={filter === f.key ? "default" : "ghost"}
              size="sm"
              className={idx > 0 ? "border-l border-neutral-300" : ""}
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
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-400" />
            <Input
              className="pl-8"
              placeholder="Search patient name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <div className="p-6 text-sm font-medium text-[#E10600]">{error}</div>
          ) : loading ? (
            <div className="p-6 font-mono text-xs uppercase text-neutral-500">
              Loading bills...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#0A0A0A] bg-[#F4F3EF] font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-700">
                  <tr>
                    <th className="px-4 py-3">Patient</th>
                    <th className="px-4 py-3">Gross (INR)</th>
                    <th className="px-4 py-3">Discount (INR)</th>
                    <th className="px-4 py-3">Net (INR)</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Created (IST)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200">
                  {bills.map((bill) => (
                    <tr key={bill.id} className="hover:bg-[#F4F3EF]/60">
                      <td className="px-4 py-2.5 font-semibold text-[#0A0A0A]">
                        {bill.patient_name}
                      </td>
                      <td className="px-4 py-2.5 font-mono tabular-nums">₹{bill.gross_amount}</td>
                      <td className="px-4 py-2.5 font-mono tabular-nums text-[#E10600]">
                        ₹{bill.discount_amount}
                      </td>
                      <td className="px-4 py-2.5 font-mono font-bold tabular-nums">
                        ₹{bill.net_amount}
                      </td>
                      <td className="px-4 py-2.5">
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
                      <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums text-neutral-500">
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
