import React, { useCallback, useEffect, useState } from "react";
import { Shield } from "lucide-react";
import { OperationPreviewCard } from "@/components/OperationPreviewCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";
import type { HospitalUserRecord, PreviewPayload } from "@/types/api";

export function UsersPage() {
  const [users, setUsers] = useState<HospitalUserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingPreview, setPendingPreview] = useState<PreviewPayload | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getUsers();
      setUsers(res.users);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to load hospital users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const requestOverridePreview = async (
    targetUser: HospitalUserRecord,
    action: "deny_permission" | "remove_override",
    permissionKey: string
  ) => {
    setError(null);
    try {
      const preview = await api.createPreview(
        "users.manage_access",
        {
          action,
          target_user_id: targetUser.id,
          permission_key: permissionKey,
        },
        `Admin UI: ${action} ${permissionKey} for ${targetUser.email}`
      );
      setPendingPreview(preview);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Access change denied.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-slate-200/90 bg-white p-6 shadow-sm">
        <div className="inline-flex rounded-full bg-indigo-50 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-indigo-700">
          04 // Identity &amp; Governance
        </div>
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">
          Hospital Users &amp; Access Control
        </h1>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
          {error}
        </div>
      )}

      {pendingPreview && (
        <Card>
          <CardContent>
            <OperationPreviewCard
              preview={pendingPreview}
              onResolved={() => {
                setPendingPreview(null);
                load();
              }}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Staff Directory &amp; Permission Overrides</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 font-mono text-xs text-slate-500">Loading users...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Staff Member</th>
                    <th className="px-5 py-3">Roles</th>
                    <th className="px-5 py-3">User Overrides</th>
                    <th className="px-5 py-3">Quick Safeguarded Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((u) => {
                    const hasInvDeny = u.overrides.some(
                      (o) => o.permission_key === "inventory.update" && o.effect === "DENY"
                    );
                    const canInvUpdate = u.effective_permissions?.["inventory.update"]?.allowed;
                    return (
                      <tr key={u.id} className="hover:bg-slate-50/70">
                        <td className="px-5 py-3">
                          <div className="font-bold text-slate-900">{u.full_name}</div>
                          <div className="font-mono text-[11px] text-slate-500">{u.email}</div>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex flex-wrap gap-1">
                            {u.roles.map((r) => (
                              <Badge key={r} variant="info">
                                {r}
                              </Badge>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          {u.overrides.length === 0 ? (
                            <span className="font-mono text-[11px] text-slate-400">None</span>
                          ) : (
                            <div className="flex flex-wrap gap-1">
                              {u.overrides.map((ov) => (
                                <Badge
                                  key={ov.permission_key}
                                  variant={ov.effect === "DENY" ? "danger" : "success"}
                                >
                                  {ov.permission_key}: {ov.effect}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="px-5 py-3">
                          {canInvUpdate && !u.roles.includes("Admin") && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                requestOverridePreview(u, "deny_permission", "inventory.update")
                              }
                            >
                              <Shield className="h-3.5 w-3.5" />
                              Revoke inventory.update
                            </Button>
                          )}
                          {hasInvDeny && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() =>
                                requestOverridePreview(u, "remove_override", "inventory.update")
                              }
                            >
                              Restore inventory.update
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
