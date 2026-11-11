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
    <div className="flex min-h-screen bg-[#F4F3EF] text-[#0A0A0A]">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-[#0A0A0A] bg-white md:flex">
        <div className="flex items-center gap-3 border-b border-[#0A0A0A] px-5 py-4">
          <div className="relative flex h-9 w-9 shrink-0 items-center justify-center bg-[#E10600] text-white">
            <span className="absolute h-4 w-1.5 bg-white" />
            <span className="absolute h-1.5 w-4 bg-white" />
          </div>
          <div>
            <div className="text-xs font-extrabold uppercase tracking-[0.1em] text-[#0A0A0A]">
              Hospital Ops
            </div>
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-neutral-500">
              AI Control // RBAC
            </div>
          </div>
        </div>

        <div className="border-b border-neutral-300 bg-[#F4F3EF]/70 px-5 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-600">
          Navigation Index
        </div>

        <nav className="flex-1 divide-y divide-neutral-200 border-b border-neutral-200">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`group flex items-center justify-between border-l-4 px-4 py-3 text-xs font-semibold uppercase tracking-[0.06em] transition ${
                  active
                    ? "border-l-[#E10600] bg-[#0A0A0A] text-white"
                    : "border-l-transparent bg-white text-neutral-700 hover:bg-[#F4F3EF] hover:text-[#0A0A0A]"
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <Icon className={`h-3.5 w-3.5 ${active ? "text-[#E10600]" : "text-neutral-500"}`} />
                  {item.label}
                </span>
                <span
                  className={`font-mono text-[10px] ${
                    active ? "text-neutral-300" : "text-neutral-400"
                  }`}
                >
                  {item.index}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-[#0A0A0A] bg-[#F4F3EF]/60 p-4">
          <div className="border border-[#0A0A0A] bg-white p-3 text-xs">
            <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-neutral-500">
              Active Operator
            </div>
            <div className="mt-1 font-bold text-[#0A0A0A]">{user?.full_name}</div>
            <div className="truncate font-mono text-[11px] text-neutral-600">{user?.email}</div>
            <div className="mt-2.5 flex flex-wrap gap-1">
              {user?.roles.map((r) => (
                <Badge key={r} variant="info">
                  {r}
                </Badge>
              ))}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-3 w-full justify-between"
            onClick={logout}
          >
            <span>Sign Out</span>
            <LogOut className="h-3.5 w-3.5" />
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#0A0A0A] bg-white px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="relative flex h-6 w-6 items-center justify-center bg-[#E10600] md:hidden">
              <span className="absolute h-3 w-1 bg-white" />
              <span className="absolute h-1 w-3 bg-white" />
            </div>
            <Building2 className="hidden h-4 w-4 text-[#E10600] md:block" />
            <span className="text-xs font-extrabold uppercase tracking-[0.1em] text-[#0A0A0A]">
              {user?.hospital_name}
            </span>
            <span className="hidden font-mono text-[10px] uppercase tracking-[0.1em] text-neutral-400 sm:inline">
              // ASIA/KOLKATA (IST)
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="hidden font-mono text-[11px] text-neutral-600 sm:inline">
              {user?.full_name}
            </span>
            {user?.roles.map((r) => (
              <Badge key={r} variant="danger">
                {r}
              </Badge>
            ))}
            <Button variant="outline" size="sm" className="md:hidden" onClick={logout}>
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        </header>

        <nav className="flex overflow-x-auto border-b border-[#0A0A0A] bg-white md:hidden">
          {navItems.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`whitespace-nowrap border-r border-neutral-300 px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.08em] ${
                  active ? "bg-[#0A0A0A] text-white" : "text-neutral-700"
                }`}
              >
                {item.index} {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="mx-auto w-full max-w-[1440px] flex-1 p-5 sm:p-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
