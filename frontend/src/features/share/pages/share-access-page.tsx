import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import { shareApi } from "@/features/share/share-api";
import { normalizeApiError } from "@/shared/api/errors";
import { formatBytes } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

export function ShareAccessPage() {
  const { token } = useParams();
  const [password, setPassword] = useState("");

  const mutation = useMutation({
    mutationFn: () => shareApi.access(token!, password || undefined),
    onError: (error) => toast.error(normalizeApiError(error).message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>访问分享文档</CardTitle>
        <CardDescription>输入访问密码（若设置）后可查看共享文档信息。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="password">访问密码（可选）</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="如果分享方设置了密码，请输入"
          />
        </div>
        <Button className="w-full" onClick={() => mutation.mutate()} disabled={!token || mutation.isPending}>
          {mutation.isPending ? "验证中..." : "访问共享内容"}
        </Button>

        {mutation.data ? (
          <div className="rounded-md border border-border bg-black/20 p-3 text-sm">
            <p className="font-medium text-primary">{mutation.data.fileName}</p>
            <p className="text-muted-foreground">文件大小：{formatBytes(mutation.data.fileSize)}</p>
            <p className="text-muted-foreground">
              下载权限：{mutation.data.allowDownload ? "允许下载（接口待接入）" : "仅可浏览"}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

