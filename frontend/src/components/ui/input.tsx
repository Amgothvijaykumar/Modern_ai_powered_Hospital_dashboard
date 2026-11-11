import React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-none border border-[#0A0A0A] bg-white px-3 py-1.5 text-sm text-[#0A0A0A] placeholder:text-neutral-400 focus:border-[#E10600] focus:outline-none focus:ring-1 focus:ring-[#E10600] disabled:cursor-not-allowed disabled:bg-neutral-100",
        className
      )}
      {...props}
    />
  );
});
Input.displayName = "Input";
