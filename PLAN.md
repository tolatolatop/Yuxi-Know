## 正式方案规划（多用户 MCP Token）

### 目标
- 支持多用户为 MCP 配置独立 token（当前假设 token = user_id）
- 每次建立 MCP 连接时注入正确的用户身份
- 避免跨用户缓存污染，保证安全与可观测性

### 方案概要
- 用户级配置：为用户保存 MCP token（当前先用 user_id 占位）
- 运行时注入：在 MCP 连接建立时动态注入 `x-user-id`
- 缓存隔离：工具缓存按 `server_name + user_id` 分区，或仅缓存与用户无关的工具元信息

### 关键改动点（待实施）
- 数据模型：
  - 用户配置中增加 `mcp_token`（或复用现有字段，明确语义）
- 请求链路：
  - 在 `chat_router` 的 `input_context` 中携带 `mcp_token`（或 user_id）
  - Agent 工具获取链路传递 `mcp_token`
- MCP 连接：
  - 在创建 session 前合并 headers，注入 `x-user-id`
  - 或通过 `httpx_client_factory` 基于上下文动态生成 headers
- 缓存策略：
  - 按用户分区缓存，避免跨用户混用
  - 或将工具缓存拆分为“用户无关的 schema”与“用户相关的连接信息”

### 风险与注意事项
- 缓存膨胀：用户数大时需要清理策略
- 安全性：日志和监控中应避免记录明文 token
- 兼容性：若 MCP 服务器采用其他鉴权头，需要统一配置映射
