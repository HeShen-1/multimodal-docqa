# Frontend

前端用于展示文档中心、工作台问答、分享访问和错误状态。

## 启动

```bash
cd frontend
npm install
npm run typecheck
npm run test
npm run build
npm run dev
```

## 页面

- `/login`：登录
- `/documents`：上传、标签、分享、详情
- `/workspace`：会话与流式问答
- `/share/:token`：分享访问
- `/analysis`：扩展分析能力

## E2E

```bash
npm run test:e2e
```

当前已补一条 mocked 主流程：登录 → 上传 → 流式问答 → 分享访问。

## 说明

- 刷新受保护页面时会先完成鉴权状态 hydrate，再决定是否跳转登录
- 详细演示路径和卖点说明请看仓库根 `README.md`
