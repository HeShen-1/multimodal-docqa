# Product Manual

## Pipeline

系统主链路为：上传文档 → 解析与切块 → 向量化 → 检索 → 流式回答 → 分享访问。

## Supported Files

当前稳定支持的文件类型包括：PDF、DOCX、TXT、Markdown、CSV、JSON。

## Upload Rules

- 单次批量上传最多 10 个文件。
- 默认问答检索 `top_k=5`。
- 上传后先写入数据库，再进入处理流程。

## Share Capability

- 支持设置访问密码。
- 支持设置过期时间。
- 支持控制是否允许下载原文件。

## UI Demo

演示推荐路径为：登录 → 文档中心上传 → 工作台流式问答 → 生成分享链接 → 访问分享页。
