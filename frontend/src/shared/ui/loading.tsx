export function Loading({ text = "加载中..." }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary" />
      <span>{text}</span>
    </div>
  );
}

