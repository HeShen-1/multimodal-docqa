import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { authApi } from "@/features/auth/auth-api";
import { normalizeApiError } from "@/shared/api/errors";
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

const schema = z
  .object({
    username: z.string().min(3, "用户名至少 3 位"),
    email: z.string().email("邮箱格式不正确"),
    password: z
      .string()
      .min(8, "密码至少 8 位")
      .regex(/[a-zA-Z]/, "密码需要包含字母")
      .regex(/[0-9]/, "密码需要包含数字"),
    confirmPassword: z.string().min(8, "请再次输入密码"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "两次密码输入不一致",
    path: ["confirmPassword"],
  });

type FormValues = z.infer<typeof schema>;

export function RegisterPage() {
  const navigate = useNavigate();
  const { register, handleSubmit, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const mutation = useMutation({
    mutationFn: async (values: FormValues) =>
      authApi.register({
        username: values.username.trim(),
        email: values.email.trim().toLowerCase(),
        password: values.password,
      }),
    onSuccess: () => {
      toast.success("注册成功，请登录");
      navigate("/login");
    },
    onError: (error) => {
      toast.error(normalizeApiError(error).message);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>创建账号</CardTitle>
        <CardDescription>注册后可使用文档问答、分享和分析功能。</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-3" onSubmit={handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="username">用户名</Label>
            <Input id="username" {...register("username")} />
            {formState.errors.username?.message ? (
              <p className="text-xs text-destructive">{formState.errors.username.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">邮箱</Label>
            <Input id="email" type="email" {...register("email")} />
            {formState.errors.email?.message ? (
              <p className="text-xs text-destructive">{formState.errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input id="password" type="password" {...register("password")} />
            {formState.errors.password?.message ? (
              <p className="text-xs text-destructive">{formState.errors.password.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">确认密码</Label>
            <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
            {formState.errors.confirmPassword?.message ? (
              <p className="text-xs text-destructive">{formState.errors.confirmPassword.message}</p>
            ) : null}
          </div>

          <Button className="w-full" type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "注册中..." : "注册"}
          </Button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          已有账号？{" "}
          <Link to="/login" className="text-primary underline underline-offset-4">
            立即登录
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
