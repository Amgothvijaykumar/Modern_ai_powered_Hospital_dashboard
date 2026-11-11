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
    <div className="space-y-4">
      <div className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm">
        <div className="inline-flex rounded-full bg-amber-50 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-amber-800">
          05 // Compliance &amp; Telemetry
        </div>
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">
          Immutable Audit Log ({total})
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Operational Attempts &amp; Policy Decisions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {error ? (
            <div className="p-6 text-sm font-medium text-rose-600">{error}</div>
          ) : loading ? (
            <div className="p-6 font-mono text-xs text-slate-500">
              Loading audit logs...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Timestamp</th>
                    <th className="px-5 py-3">Query</th>
                    <th className="px-5 py-3">Operation</th>
                    <th className="px-5 py-3">Auth Result</th>
                    <th className="px-5 py-3">Exec Status</th>
                    <th className="px-5 py-3">Rows</th>
                    <th className="px-5 py-3">Decision Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/70">
                      <td className="whitespace-nowrap px-5 py-3 font-mono text-[11px] tabular-nums text-slate-500">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="max-w-[220px] truncate px-5 py-3 font-semibold text-slate-900">
                        {log.raw_user_query}
                      </td>
                      <td className="px-5 py-3 font-mono text-[11px]">
                        {log.operation || "—"}
                      </td>
                      <td className="px-5 py-3">
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
                      <td className="px-5 py-3">
                        <Badge variant="outline">{log.execution_status}</Badge>
                      </td>
                      <td className="px-5 py-3 font-mono tabular-nums">
                        {log.affected_rows ?? "—"}
                      </td>
                      <td className="max-w-[280px] px-5 py-3 text-slate-600">
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
