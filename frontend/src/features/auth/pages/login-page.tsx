import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { authApi } from "@/features/auth/auth-api";
import { normalizeApiError } from "@/shared/api/errors";
import { useAuthStore } from "@/shared/store/auth-store";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

const schema = z.object({
  username: z.string().min(1, "请输入用户名或邮箱"),
  password: z.string().min(1, "请输入密码"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuthStore((state) => state.setTokens);
  const setUser = useAuthStore((state) => state.setUser);
  const from = (location.state as { from?: string } | null)?.from ?? "/workspace";

  const { register, handleSubmit, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: "",
      password: "",
    },
  });

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const tokens = await authApi.login({
        ...values,
        username: values.username.trim(),
      });
      setTokens(tokens);
      const me = await authApi.getMe();
      setUser(me);
      return me;
    },
    onSuccess: () => {
      toast.success("登录成功");
      navigate(from, { replace: true });
    },
    onError: (error) => {
      const apiError = normalizeApiError(error);
      toast.error(apiError.message);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>欢迎回到 DocQA</CardTitle>
        <CardDescription>登录后进入对话、文档和分析工作台。</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="username">用户名 / 邮箱</Label>
            <Input id="username" placeholder="alice@example.com" {...register("username")} />
            {formState.errors.username?.message ? (
              <p className="text-xs text-destructive">{formState.errors.username.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input id="password" type="password" placeholder="••••••••" {...register("password")} />
            {formState.errors.password?.message ? (
              <p className="text-xs text-destructive">{formState.errors.password.message}</p>
            ) : null}
          </div>

          <Button className="w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "登录中..." : "登录"}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          还没有账号？{" "}
          <Link to="/register" className="text-primary underline underline-offset-4">
            立即注册
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
