import * as React from "react";

import { cn } from "@/shared/lib/utils";

export interface SelectOption {
  label: string;
  value: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[];
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, style, ...props }, ref) => (
    <select
      ref={ref}
      style={{
        colorScheme: "dark",
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23f59e0b' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
        backgroundPosition: "right 0.75rem center",
        backgroundRepeat: "no-repeat",
        backgroundSize: "0.95rem",
        ...style,
      }}
      className={cn(
        "h-10 w-full appearance-none rounded-md border border-input bg-card/80 px-3 py-2 pr-10 text-sm text-foreground shadow-sm backdrop-blur-sm transition-colors hover:border-primary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    >
      {options.map((option) => (
        <option
          key={option.value}
          value={option.value}
          className="bg-slate-950 text-slate-100"
          style={{ backgroundColor: "#0f172a", color: "#f8fafc" }}
        >
          {option.label}
        </option>
      ))}
    </select>
  ),
);
Select.displayName = "Select";
