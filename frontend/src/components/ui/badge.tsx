import React from "react";
import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "bg-[#F4F3EF] text-[#0A0A0A] border-neutral-400",
    success: "bg-emerald-50 text-emerald-900 border-emerald-700",
    warning: "bg-amber-50 text-amber-950 border-amber-700",
    danger: "bg-[#FFF2F2] text-[#E10600] border-[#E10600]",
    info: "bg-[#0A0A0A] text-white border-[#0A0A0A]",
    outline: "bg-white text-neutral-700 border-neutral-400",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-none border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.08em]",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
