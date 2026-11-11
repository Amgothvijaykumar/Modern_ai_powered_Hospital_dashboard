import React from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  Building2,
  ClipboardList,
  FileText,
  LogOut,
  Package,
  Users,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function DashboardLayout() {
  const { user, logout, hasPermission } = useAuth();
  const location = useLocation();

  const navItems = [
    { index: "01", to: "/", label: "Assistant & Overview", icon: Activity, visible: true },
    { index: "02", to: "/inventory", label: "Inventory", icon: Package, visible: hasPermission("inventory.read") },
    { index: "03", to: "/bills", label: "Billing Ledger", icon: FileText, visible: hasPermission("bills.read") },
    { index: "04", to: "/users", label: "Users & Access", icon: Users, visible: hasPermission("users.read") },
    {
      index: "05",
      to: "/audit-logs",
      label: "Audit History",
      icon: ClipboardList,
      visible: Boolean(user?.roles.includes("Admin")),
    },
  ].filter((item) => item.visible);

  return (
    <div className="min-h-screen bg-[#F3F5F8] p-3 text-slate-950 sm:p-4 lg:p-5">
      <div className="mx-auto flex max-w-[1520px] flex-col gap-4 md:flex-row">
        {/* Bento Sidebar Rail */}
        <aside className="hidden w-64 shrink-0 flex-col justify-between rounded-3xl border border-slate-200/90 bg-white p-4 shadow-sm md:sticky md:top-5 md:flex md:h-[calc(100vh-2.5rem)]">
          <div>
            <div className="flex items-center gap-3 rounded-2xl bg-slate-950 px-3.5 py-3 text-white">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white">
                <Activity className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-extrabold tracking-tight">MEDOPS AI</div>
                <div className="font-mono text-[10px] text-slate-400">Hospital Control</div>
              </div>
            </div>

            <div className="mt-5 px-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Workspace Modules
            </div>

            <nav className="mt-2 space-y-1.5">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = location.pathname === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center justify-between rounded-2xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
                      active
                        ? "bg-slate-950 text-white shadow-sm"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <Icon className={`h-4 w-4 ${active ? "text-indigo-400" : "text-slate-400"}`} />
                      {item.label}
                    </span>
                    <span
                      className={`font-mono text-[10px] ${
                        active ? "text-slate-400" : "text-slate-400"
                      }`}
                    >
                      {item.index}
                    </span>
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="space-y-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3.5 text-xs">
              <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
                Active Operator
              </div>
              <div className="mt-1 font-bold text-slate-950">{user?.full_name}</div>
              <div className="truncate font-mono text-[11px] text-slate-500">{user?.email}</div>
              <div className="mt-2.5 flex flex-wrap gap-1">
                {user?.roles.map((r) => (
                  <Badge key={r} variant="info">
                    {r}
                  </Badge>
                ))}
              </div>
            </div>
            <Button variant="outline" size="sm" className="w-full justify-between" onClick={logout}>
              <span>Sign Out</span>
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </aside>

        {/* Main Content Column */}
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          {/* Top Bento Header Bar */}
          <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/90 bg-white px-5 py-3 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                <Building2 className="h-4 w-4" />
              </div>
              <div>
                <div className="text-sm font-bold tracking-tight text-slate-950">
                  {user?.hospital_name}
                </div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400">
                  Multi-Tenant RBAC · Asia/Kolkata (IST)
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <span className="hidden text-xs font-medium text-slate-600 sm:inline">
                {user?.full_name}
              </span>
              {user?.roles.map((r) => (
                <Badge key={r} variant="info">
                  {r}
                </Badge>
              ))}
              <Button variant="outline" size="sm" className="md:hidden" onClick={logout}>
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            </div>
          </header>

          {/* Mobile Bento Navigation Strip */}
          <nav className="flex gap-2 overflow-x-auto pb-1 md:hidden">
            {navItems.map((item) => {
              const active = location.pathname === item.to;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`whitespace-nowrap rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
                    active
                      ? "border-slate-950 bg-slate-950 text-white"
                      : "border-slate-200 bg-white text-slate-700"
                  }`}
                >
                  {item.index} · {item.label}
                </Link>
              );
            })}
          </nav>

          <main className="min-w-0 flex-1">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
