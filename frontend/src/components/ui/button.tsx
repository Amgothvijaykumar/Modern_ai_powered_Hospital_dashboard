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
    default: "bg-[#0A0A0A] text-white hover:bg-[#E10600] border border-[#0A0A0A] hover:border-[#E10600]",
    secondary: "bg-[#F4F3EF] text-[#0A0A0A] border border-neutral-400 hover:border-[#0A0A0A] hover:bg-white",
    outline: "border border-[#0A0A0A] bg-white text-[#0A0A0A] hover:bg-[#0A0A0A] hover:text-white",
    destructive: "bg-[#E10600] text-white border border-[#E10600] hover:bg-red-800",
    ghost: "text-[#0A0A0A] hover:bg-neutral-200/70 border border-transparent",
  };
  const sizes = {
    sm: "h-8 px-3 text-[11px] uppercase tracking-[0.08em]",
    md: "h-9 px-4 text-xs uppercase tracking-[0.08em]",
    lg: "h-11 px-6 text-xs uppercase tracking-[0.1em]",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-none font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E10600] focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-40",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
