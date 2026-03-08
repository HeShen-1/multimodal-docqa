import { Outlet } from "react-router-dom";

export function PublicLayout() {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_20%,rgba(244,114,182,.2),transparent_30%),radial-gradient(circle_at_10%_80%,rgba(56,189,248,.2),transparent_24%)]" />
      <div className="relative w-full max-w-md">
        <Outlet />
      </div>
    </div>
  );
}

