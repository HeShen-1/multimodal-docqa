import { expect, test } from "@playwright/test";

type DocumentState = {
  id: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  status: "completed";
  description: string;
  pageCount: number;
  chunkCount: number;
  imageCount: number;
  createdAt: string;
  updatedAt: string;
};

type ShareState = {
  id: string;
  documentId: string;
  token: string;
  shareUrl: string;
  hasPassword: boolean;
  allowDownload: boolean;
  expiresAt: string;
  accessCount: number;
  maxAccessCount: number | null;
  createdAt: string;
};

function envelope(data: unknown) {
  return {
    code: 100000,
    message: "success",
    data,
  };
}

test("main demo flow works with mocked backend", async ({ page }) => {
  const now = "2026-03-07T10:00:00.000Z";
  let documents: DocumentState[] = [];
  let shares: ShareState[] = [];
  let messages: Array<Record<string, unknown>> = [];

  const buildConversation = () => ({
    id: "conv-1",
    userId: "user-1",
    title: "项目演示会话",
    documentIds: documents.length ? ["doc-1"] : [],
    messageCount: messages.length,
    lastMessage: (messages.at(-1)?.content as string | undefined) ?? "欢迎体验项目演示",
    createdAt: now,
    updatedAt: now,
  });

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const method = request.method();

    if (pathname.endsWith("/auth/login") && method === "POST") {
      return route.fulfill({ json: envelope({ access_token: "token", refresh_token: "refresh", token_type: "bearer", expires_in: 3600 }) });
    }

    if (pathname.endsWith("/auth/me") && method === "GET") {
      return route.fulfill({
        json: envelope({
          id: "user-1",
          username: "demo-user",
          email: "demo@example.com",
          role: "user",
          isActive: true,
          createdAt: now,
          documentCount: documents.length,
          queryCount: messages.length,
          storageUsed: documents.reduce((total, item) => total + item.fileSize, 0),
        }),
      });
    }

    if (pathname.endsWith("/documents") && method === "GET") {
      return route.fulfill({
        json: envelope({
          items: documents,
          total: documents.length,
          page: 1,
          pageSize: 8,
          totalPages: 1,
        }),
      });
    }

    if (pathname.endsWith("/documents/upload") && method === "POST") {
      documents = [
        {
          id: "doc-1",
          fileName: "demo.txt",
          fileType: ".txt",
          fileSize: 23,
          status: "completed",
          description: "演示文档",
          pageCount: 1,
          chunkCount: 1,
          imageCount: 0,
          createdAt: now,
          updatedAt: now,
        },
      ];
      return route.fulfill({ json: envelope(documents[0]) });
    }

    if (pathname.endsWith("/share/documents/doc-1") && method === "GET") {
      return route.fulfill({ json: envelope(shares) });
    }

    if (pathname.endsWith("/share/documents/doc-1") && method === "POST") {
      shares = [
        {
          id: "share-1",
          documentId: "doc-1",
          token: "share-token",
          shareUrl: "http://127.0.0.1:5173/share/share-token",
          hasPassword: false,
          allowDownload: true,
          expiresAt: "2026-03-08T10:00:00.000Z",
          accessCount: 0,
          maxAccessCount: null,
          createdAt: now,
        },
      ];
      return route.fulfill({ json: envelope(shares[0]) });
    }

    if (pathname.endsWith("/share/share-token/access") && method === "POST") {
      return route.fulfill({
        json: envelope({
          documentId: "doc-1",
          fileName: "demo.txt",
          fileSize: 23,
          allowDownload: true,
        }),
      });
    }

    if (pathname.endsWith("/documents/doc-1") && method === "GET") {
      return route.fulfill({
        json: envelope({
          ...documents[0],
          metadata: { source: "playwright" },
          previewText: "这是一个用于演示登录、上传、问答和分享链路的文档。",
        }),
      });
    }

    if (pathname.endsWith("/documents/doc-1/chunks") && method === "GET") {
      return route.fulfill({
        json: envelope([
          {
            id: "chunk-1",
            content: "该文档展示了上传、检索、流式回答和分享访问的完整链路。",
            page: 1,
            chunkIndex: 0,
            length: 28,
            type: "text",
          },
        ]),
      });
    }

    if (pathname.endsWith("/documents/doc-1/tags") && method === "GET") {
      return route.fulfill({ json: envelope([]) });
    }

    if (pathname.endsWith("/tags") && method === "GET") {
      return route.fulfill({
        json: envelope({
          items: [],
          total: 0,
          page: 1,
          pageSize: 50,
          totalPages: 1,
        }),
      });
    }

    if (pathname.endsWith("/conversations") && method === "GET") {
      return route.fulfill({
        json: envelope({
          total: 1,
          conversations: [buildConversation()],
        }),
      });
    }

    if (pathname.endsWith("/conversations/conv-1") && method === "GET") {
      return route.fulfill({
        json: envelope({
          ...buildConversation(),
          messages,
        }),
      });
    }

    if (pathname.endsWith("/conversations/conv-1/messages/stream") && method === "POST") {
      const requestBody = request.postDataJSON() as { content?: string };
      const userContent = requestBody.content ?? "";
      const assistantContent = "结论：系统已经打通上传、检索、流式回答与分享访问链路。";
      messages = [
        {
          id: "msg-user-1",
          conversationId: "conv-1",
          role: "user",
          content: userContent,
          createdAt: now,
        },
        {
          id: "msg-assistant-1",
          conversationId: "conv-1",
          role: "assistant",
          content: assistantContent,
          thinking: [
            { step: "问题分析", content: "用户在确认项目主链路是否完整。" },
            { step: "证据筛选", content: "已命中演示文档中的完整流程描述。" },
          ],
          sources: [
            {
              type: "source",
              fileName: "demo.txt",
              page: 1,
              content: "该文档展示了上传、检索、流式回答和分享访问的完整链路。",
            },
          ],
          createdAt: now,
        },
      ];
      const body = [
        `data: ${JSON.stringify({ type: "thinking", step: "问题分析", content: "用户在确认主链路是否完整。" })}\n\n`,
        `data: ${JSON.stringify({ type: "source", fileName: "demo.txt", page: 1, content: "该文档展示了上传、检索、流式回答和分享访问的完整链路。" })}\n\n`,
        `data: ${JSON.stringify({ type: "answer", content: "结论：系统已经打通上传、检索、流式回答与分享访问链路。" })}\n\n`,
        `data: ${JSON.stringify({ type: "done" })}\n\n`,
      ].join("");
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    }

    return route.fulfill({ status: 404, json: { detail: `${method} ${pathname} not mocked` } });
  });

  await page.goto("/login");
  await page.getByLabel("用户名 / 邮箱").fill("demo-user");
  await page.getByLabel("密码").fill("password123");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "项目演示会话" })).toBeVisible();

  await page.goto("/documents");
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "demo.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("demo project document"),
  });
  await page.getByRole("button", { name: "上传并开始处理" }).click();
  const documentButton = page.getByRole("button", { name: /demo\.txt/ }).first();
  await expect(documentButton).toBeVisible();
  await documentButton.click();
  await page.getByRole("button", { name: "生成分享链接" }).click();
  await expect(page.getByText("http://127.0.0.1:5173/share/share-token")).toBeVisible();

  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "项目演示会话" })).toBeVisible();
  await page.getByPlaceholder("输入问题，例如：请总结这份文档的核心结论。").fill("这个项目主链路是否已经跑通？");
  await page.getByRole("button", { name: "发送消息" }).click();
  await expect(
    page.getByText("结论：系统已经打通上传、检索、流式回答与分享访问链路。").last(),
  ).toBeVisible();

  await page.goto("/share/share-token");
  await page.getByRole("button", { name: "访问共享内容" }).click();
  await expect(page.getByText("demo.txt")).toBeVisible();
  await expect(page.getByText("允许下载（接口待接入）")).toBeVisible();
});
