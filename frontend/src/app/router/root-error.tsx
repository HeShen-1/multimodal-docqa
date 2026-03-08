import { Link, useRouteError } from "react-router-dom";

export function RootErrorBoundary() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : "未知路由错误";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center">
      <h1 className="font-heading text-4xl text-primary">Oops</h1>
      <p className="text-muted-foreground">{message}</p>
      <Link to="/workspace" className="text-primary underline underline-offset-4">
        返回工作台
      </Link>
    </div>
  );
}

