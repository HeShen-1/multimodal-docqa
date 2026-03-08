import { cn } from "@/shared/lib/utils";

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}

export function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2">
      <button
        type="button"
        aria-pressed={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 rounded-full border transition",
          checked ? "border-primary bg-primary/40" : "border-border bg-muted",
        )}
      >
        <span
          className={cn(
            "absolute left-0.5 top-0.5 h-4.5 w-4.5 rounded-full bg-white transition-transform",
            checked && "translate-x-5",
          )}
        />
      </button>
      {label ? <span className="text-sm text-muted-foreground">{label}</span> : null}
    </label>
  );
}

