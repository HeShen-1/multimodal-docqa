import { LogOut } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { authApi } from "@/features/auth/auth-api";
import { cn } from "@/shared/lib/utils";
import { useAuthStore } from "@/shared/store/auth-store";
import { Button } from "@/shared/ui/button";

const navItems = [
  { to: "/workspace", label: "对话工作台" },
  { to: "/documents", label: "文档中心" },
  { to: "/analysis", label: "智能分析" },
];

export function PrivateLayout() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const meQuery = useQuery({
    queryKey: ["auth-me"],
    queryFn: authApi.getMe,
    enabled: !user,
    retry: 0,
  });

  useEffect(() => {
    if (meQuery.data) {
      setUser(meQuery.data);
    }
  }, [meQuery.data, setUser]);

  const onLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      // noop
    }
    clearAuth();
    navigate("/login");
  };

  return (
    <div className="mx-auto min-h-screen max-w-[1440px] px-4 pb-8 pt-4">
      <header className="glass-panel mb-6 flex items-center justify-between px-4 py-3">
        <div>
          <p className="font-heading text-lg text-primary">Multimodal DocQA</p>
          <p className="text-xs text-muted-foreground">Editorial Intelligence Console</p>
        </div>

        <nav className="flex items-center gap-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "rounded-full px-3 py-1.5 text-sm text-muted-foreground transition",
                  isActive && "bg-primary/20 text-primary",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">{user?.username ?? "用户"}</span>
          <Button variant="secondary" size="sm" onClick={onLogout}>
            <LogOut className="h-4 w-4" />
            退出
          </Button>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
