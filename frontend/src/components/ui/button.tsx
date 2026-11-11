import React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "destructive" | "ghost" | "secondary";
  size?: "sm" | "md" | "lg";
}

export function Button({
  className,
  variant = "default",
  size = "md",
  ...props
}: ButtonProps) {
  const variants = {
    default:
      "bg-slate-950 text-white hover:bg-indigo-600 shadow-sm",
    secondary:
      "bg-slate-100 text-slate-900 hover:bg-slate-200 border border-slate-200",
    outline:
      "border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 hover:border-slate-300",
    destructive:
      "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
    ghost:
      "text-slate-700 hover:bg-slate-100",
  };
  const sizes = {
    sm: "h-8 rounded-xl px-3 text-xs",
    md: "h-10 rounded-xl px-4 text-sm",
    lg: "h-11 rounded-2xl px-6 text-sm",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-45",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
