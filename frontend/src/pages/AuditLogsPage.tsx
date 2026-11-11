import React, { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { AuditLogRecord } from "@/types/api";

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.getAuditLogs({ limit: 50 });
        setLogs(res.items);
        setTotal(res.total_count);
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Unable to load audit history.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-5">
      <div className="border-b-2 border-[#0A0A0A] pb-4">
        <div className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-[#E10600]">
          05 // Compliance &amp; Telemetry
        </div>
        <h1 className="mt-1 text-2xl font-extrabold uppercase tracking-tight text-[#0A0A0A]">
          Immutable Audit Log ({total})
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Operational Attempts &amp; Policy Decisions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <div className="p-6 text-sm font-medium text-[#E10600]">{error}</div>
          ) : loading ? (
            <div className="p-6 font-mono text-xs uppercase text-neutral-500">
              Loading audit logs...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-[#0A0A0A] bg-[#F4F3EF] font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-700">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Query</th>
                    <th className="px-4 py-3">Operation</th>
                    <th className="px-4 py-3">Auth Result</th>
                    <th className="px-4 py-3">Exec Status</th>
                    <th className="px-4 py-3">Rows</th>
                    <th className="px-4 py-3">Decision Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-200">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-[#F4F3EF]/60">
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[11px] tabular-nums text-neutral-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="max-w-[220px] truncate px-4 py-2.5 font-semibold text-[#0A0A0A]">
                        {log.raw_user_query}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[11px]">
                        {log.operation || "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge
                          variant={
                            log.authorization_result === "ALLOWED"
                              ? "success"
                              : log.authorization_result === "DENIED"
                              ? "danger"
                              : "warning"
                          }
                        >
                          {log.authorization_result}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge variant="outline">{log.execution_status}</Badge>
                      </td>
                      <td className="px-4 py-2.5 font-mono tabular-nums">
                        {log.affected_rows ?? "—"}
                      </td>
                      <td className="max-w-[280px] px-4 py-2.5 text-neutral-700">
                        {log.decision_reason}
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
