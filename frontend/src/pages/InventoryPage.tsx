import React, { useCallback, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import type { InventoryItemRecord } from "@/types/api";

export function InventoryPage() {
  const [items, setItems] = useState<InventoryItemRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getInventory({
        filter,
        search: search.trim() || undefined,
        limit: 50,
      });
      setItems(res.items);
      setTotal(res.total_count);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load inventory.");
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
            02 // Inventory Catalog
          </div>
          <h1 className="mt-1 text-2xl font-extrabold uppercase tracking-tight text-[#0A0A0A]">
            Hospital Inventory ({total})
          </h1>
        </div>

        <div className="flex flex-wrap border border-[#0A0A0A] bg-white">
          {[
            { key: "all", label: "All" },
            { key: "low_stock", label: "Low Stock" },
            { key: "expiring_soon", label: "Expiring (30d)" },
            { key: "out_of_stock", label: "Out of Stock" },
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
          <CardTitle>Inventory Records Ledger</CardTitle>
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-400" />
            <Input
              className="pl-8"
              placeholder="Search item name..."
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
              Loading inventory...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#0A0A0A] bg-[#F4F3EF] font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-700">
                  <tr>
                    <th className="px-4 py-3">Item Name</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Quantity</th>
                    <th className="px-4 py-3">Min Qty</th>
                    <th className="px-4 py-3">Unit Price</th>
                    <th className="px-4 py-3">Expiry</th>
                    <th className="px-4 py-3">Batch</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200">
                  {items.map((item) => (
                    <tr key={item.id} className="hover:bg-[#F4F3EF]/60">
                      <td className="px-4 py-2.5 font-semibold text-[#0A0A0A]">{item.item_name}</td>
                      <td className="px-4 py-2.5 text-neutral-600">{item.category}</td>
                      <td className="px-4 py-2.5 font-mono tabular-nums">
                        <Badge variant={item.is_low_stock ? "danger" : "success"}>
                          {item.quantity}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 font-mono tabular-nums text-neutral-600">
                        {item.minimum_quantity}
                      </td>
                      <td className="px-4 py-2.5 font-mono tabular-nums">₹{item.unit_price}</td>
                      <td className="px-4 py-2.5 font-mono text-[11px] tabular-nums text-neutral-600">
                        {item.expiry_date}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11px] text-neutral-500">
                        {item.batch_number}
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
