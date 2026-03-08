# Operations Policy

## Truth Source

文档元数据、分享链接、状态查询的业务判断统一以数据库为真相源；进程内缓存仅用于临时进度展示。

## Health

- `/health` 返回简化健康摘要。
- `/health/detailed` 返回数据库、Redis、LLM、向量检索、资源使用情况。
- `/stats` 统计文档数、查询数、切块数、图片数、平均处理耗时与存储占用。

## Access Control

- `documents` 相关接口默认要求登录。
- `share` 创建、列表、撤销要求登录。
- `admin` 路由仅管理员可访问。

## Logging

每个请求需要记录请求 ID、用户、路径、耗时和错误原因。

## Degradation

系统存在 L0-L3 降级等级，在无证据场景下优先返回受限回答，避免编造。
