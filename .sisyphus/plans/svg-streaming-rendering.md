# SVG 流式渲染支持计划（更新版）

## TL;DR
> **概要**：支持将 LLM 在流式聊天消息和知识库内容中输出的 SVG 图像渲染出来。SVG 以 ` ```svg` 围栏代码块的形式出现；目前会被 Shiki 渲染为语法高亮的代码。需要在 markdown-it 处理前预处理 Markdown，将 SVG 代码块转换为内联 SVG HTML（DOMPurify 默认已安全支持 SVG，无需额外配置）。
>
> **交付物**：1 个工具模块、修改渲染入口（`markdown_preview.js` + `MarkdownPreview.vue`）、CSS 样式、单元测试
>
> **工作量**：短期（3-5 个任务）
>
> **并行度**：是 — 2 个波次
>
> **关键路径**：svgRenderer.js → markdown_preview.js（renderMarkdown）→ MarkdownPreview.vue（CSS）→ 测试

## 背景

### 原始需求
调研 Yuxi 的流式渲染对 SVG 显示的支持能力，确认问题，并制定一个添加 SVG 渲染能力的计划。

### 问题确认：所有 Markdown 渲染路径均不具备 SVG 渲染能力
经过全面调研，**无论是流式内容还是非流式（静态）内容，只要经过 Markdown 渲染的路径，目前都不支持 SVG 渲染**。SVG 代码块 ` ```svg ... ``` ` 在所有路径中都被 Shiki 渲染为语法高亮的代码块，而非内联 SVG 图像。

### 渲染架构总览
项目使用自建的 `MarkdownPreview.vue` 组件作为**唯一的 Markdown 渲染入口**，渲染链路统一：

```
Markdown 内容 → MarkdownPreview.vue
  → renderMarkdown() [markdown_preview.js]
    → 预处理：renderSvgBlocks() 将 ```svg → <svg>  ← 新增步骤
      → markdown-it(html:true) + Shiki（代码高亮）
        → DOMPurify.sanitize() ← ✅ 默认已安全支持 SVG
          → v-html
```

### 覆盖范围：所有 Markdown 渲染路径（6 个组件）
`MarkdownPreview` 被以下 6 个组件使用，覆盖 AI 对话的全生命周期：

| # | 组件 | 用途 | 涉及 AI 对话？ |
|---|------|------|:---:|
| 1 | `AgentMessageComponent.vue` | **AI 回复消息渲染**（流式+历史） | ✅ 核心 |
| 2 | `ToolCallingResult/tools/TaskTool.vue` | **子智能体任务结果渲染** | ✅ 是 |
| 3 | `MarkdownContentViewer.vue` | 知识库文件内容预览 | ❌ 知识库页 |
| 4 | `AgentFilePreview.vue` | 工作区文件 Markdown 预览 | ❌ 工作区 |
| 5 | `FileDetailModal.vue` | 文件详情弹窗 | ❌ 通用 |
| 6 | `KbChunkDetailModal.vue` | 知识块详情弹窗 | ❌ 知识库 |

**所有路径最终都汇聚到同一个渲染入口** `renderMarkdown()`，修改这一处即可全量覆盖。

### 访谈总结（再调研更新）
- LLM 在 ` ```svg` 围栏代码块中输出 SVG — 所有 `type === 'ai'` 的消息内容都经过 `renderMarkdown()` 渲染
- 项目**已不再使用 `md-editor-v3`**，而是使用自建的 `MarkdownPreview.vue` 组件
- 渲染链路：markdown-it（html: true）+ Shiki（代码高亮）+ **DOMPurify（XSS 过滤）** → v-html
- **关键发现**：经查阅 DOMPurify v3.4.2 源码确认，DOMPurify **默认已安全支持 SVG 标签和属性**，无需修改其配置
- 真正的瓶颈：` ```svg ` 代码块在 markdown-it 阶段被 Shiki 拦截并渲染为高亮代码，SVG 内容未到达 DOMPurify
- 方案：在 `renderMarkdown()` 函数内部、`md.render()` 之前预处理 SVG 代码块，将 ` ```svg → <svg>` 标签
- 流式安全：只转换完整的 ` ```svg ... ``` ` 代码块
- 测试：单元测试（Vitest）+ 手动 E2E 验证

### Metis 审查
不可用。已进行自我审查。

## 工作目标

### 核心目标
将 ` ```svg ... ``` ` 代码块渲染为内联 SVG 图像，覆盖 AI 对话全生命周期中所有可能出现 SVG 的渲染路径，包括：
- **流式渲染中**：AI 正在生成的过程中，完整出现的 SVG 块
- **流式完成后**：完整消息展示时
- **历史消息加载**：从后端加载的历史 AI 回复
- **子智能体任务结果**：`TaskTool.vue` 中渲染的子任务输出
- **知识库内容**：`MarkdownContentViewer.vue` 中渲染的引用内容
- **文件预览**：工作区中 Markdown 文件的 SVG 渲染

### 交付物
1. `web/src/utils/svgRenderer.js` — SVG 代码块预处理工具函数
2. 修改 `web/src/utils/markdown_preview.js` — 在 `renderMarkdown()` 中集成 SVG 预处理（DOMPurify 默认已支持，无需配置）
3. CSS 样式 — 在 `MarkdownPreview.vue` 中添加响应式 SVG 容器样式（含深色模式）
4. 单元测试 — `web/src/utils/__tests__/svgRenderer.test.js`

### 完成标准（可验证的条件与命令）
1. AI 回复消息（流式+完成态）中 ` ```svg <svg>...</svg> ``` ` 渲染为内联 SVG 图像
2. 流式传输过程中，不完整/未完成的 SVG 块保持文本形式，完成后正确渲染
3. 子智能体任务结果（TaskTool）中 SVG 正确渲染
4. 所有使用 MarkdownPreview 的组件（6 处）均支持 SVG 渲染
5. SVG 响应式缩放并适配深色模式
6. 无 XSS 风险 — SVG 内容经 DOMPurify 默认安全白名单过滤（无需额外配置）
7. 所有测试通过：`pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js`
8. 现有 Markdown 渲染（代码块、表格、图片、Katex、frontmatter 等）无回归

### 必须包含
- ` ```svg` 代码块 → 内联 SVG 渲染（覆盖所有 MarkdownPreview 使用场景）
- 流式安全性（部分代码块不破坏 UI）
- 响应式 SVG（max-width: 100%，height: auto）
- 深色模式支持
- 保持现有 DOMPurify 配置不变（默认已安全支持 SVG）

### 禁止包含（护栏、AI 套话模式、范围边界）
- 不修改后端流式逻辑
- 不修改各个业务组件（AgentMessageComponent.vue、MarkdownContentViewer.vue 等）
- 不破坏现有 Shiki 代码高亮功能
- 不添加额外外部依赖
- **不修改 DOMPurify 配置**（默认已安全支持 SVG，无需改动）
- 不通过 `v-html` 直接插入未过滤的 SVG — 必须经过 DOMPurify
- 不修改其他语言的代码块渲染方式
- 不包含 SVG 编辑/创作功能
- 不修改其他图像格式（PNG/JPG/GIF）的处理方式
- 不包括 `MdSidepanel.vue`（看板侧面板，使用 `marked` 库独立渲染，属于另一功能域）

## 验证策略
> **零人工干预** — 所有验证均由代理自动执行。
- **测试决策**：svgRenderer.js 的单元测试（Vitest）+ 手动 E2E 验证
- **QA 策略**：每个任务都有代理执行的验证场景
- **证据**：.sisyphus/evidence/task-{N}-{slug}.{ext}

## 执行策略

### 核心策略：单点修改，全量覆盖

本方案的核心优势在于：项目使用统一的 Markdown 渲染入口 `MarkdownPreview.vue` → `renderMarkdown()`，所以**只需修改 `markdown_preview.js` 一个文件**，即可让所有 6 个组件（包括流式聊天、历史消息、子任务结果、知识库内容等）同时获得 SVG 渲染能力。

### 并行执行波次

**波次 1**：[svgRenderer.js 工具 + 单元测试] — 基础，可并行
**波次 2**：[markdown_preview.js 集成 SVG 预处理 + MarkdownPreview.vue CSS] — 依赖波次 1

### 依赖矩阵（完整，所有任务）

| 任务 | 依赖 | 阻塞 | 覆盖的渲染路径 |
|------|------|------|--------------|
| 1. svgRenderer.js 工具函数 | — | 2, 4 | 工具函数，被 renderMarkdown 调用 |
| 2. markdown_preview.js 集成 SVG 预处理 | 1 | — | **所有 6 个组件的 Markdown 渲染** |
| 3. MarkdownPreview.vue CSS 样式 | — | — | 全局 SVG 容器样式 |
| 4. 单元测试 | 1 | — | 工具函数测试 |
| F1-F4. 验证 | 1,2,3,4 | — | 全量验证 |

### 代理调度摘要
- **波次 1**：2 个任务（svgRenderer.js 工具 + 单元测试）— 可并行执行
- **波次 2**：2 个任务（markdown_preview.js 集成 + CSS 样式）— 波次 1 完成后可并行
- **最终波次**：4 个并行审查代理
- **影响范围**：修改 2 个核心文件 + 1 个 CSS 文件，覆盖所有 6 个 markdown 渲染组件

## 任务列表

- [ ] 1. 创建 SVG 预处理工具函数（`web/src/utils/svgRenderer.js`）

  **任务内容**：创建一个工具函数 `renderSvgBlocks(markdown)`，负责将 Markdown 字符串中的 ` ```svg` 围栏代码块转换为内联 SVG HTML。

  **正则需要覆盖的所有围栏变体**：

  | 围栏样式 | 示例 |
  |----------|------|
  | 反引号围栏 | \`\`\`svg ... \`\`\` |
  | 波浪线围栏 | ~~~svg ... ~~~ |
  | 带缩进 | `    \`\`\`svg ...` |
  | 后缀空格 | \`\`\`svg\n\`\`\` |
  | 大写标签 | \`\`\`SVG ... \`\`\`（不区分大小写匹配） |
  | 围栏内含属性 | \`\`\`svg id="mySvg"\`\`\`（仅第一个词作为语言标识） |

  **稳健的正则策略**（分步处理，避免单一大正则的边界问题）：

  1. **第一步 — 检测并提取**：使用行级扫描匹配围栏代码块，而非单一大正则
     ```js
     // 匹配围栏开头的正则
     const FENCE_OPEN_RE = /^( {0,3})(`{3,}|~{3,})\s*(\S*)/
     // 检测 SVG 语言标识：第一个非空单词为 svg（不区分大小写）
     // 排除 backtick-fenced 内部的 ``` 误匹配
     ```

  2. **第二步 — 逐行解析**：从围栏开始行向后扫描，寻找匹配的关闭围栏
     - 关闭围栏规则：缩进 ≤ 开头缩进，同种围栏字符（\` 或 ~），长度 ≥ 开头
     - 内容行原样累积

  3. **第三步 — 条件替换**：仅当找到匹配的关闭围栏时才执行替换（流式安全的核心保证）

  4. **第四步 — 组装 HTML**：`<div class="svg-inline-render">` 包裹原始 SVG 内容

  **流式安全核心设计**：
  - 如果到字符串末尾仍未找到闭合围栏 → **原样保留**（不破坏不完整块）
  - 缩进嵌套的围栏代码块内层不触发转换（markdown-it 自身处理嵌套）

  **边缘情况清单**：
  - [ ] SVG 内容中包含反引号（如 `<title>\`code\`</title>`）— 关闭围栏在单独一行，不会误匹配
  - [ ] SVG 内容中包含空行 — 压缩为单行后不会触发 markdown-it HTML 块截断
  - [ ] 波浪线围栏 `~~~svg ... ~~~`
  - [ ] 带缩进的围栏 `    \`\`\`svg`
  - [ ] 围栏前有其他内容：`text\n\`\`\`svg\n...\n\`\`\`\nrest`
  - [ ] 多个不连续的 SVG 块
  - [ ] 连续多个 SVG 块
  - [ ] 空的 SVG 代码块 `\`\`\`svg\n\`\`\`` — 转换为空容器或保留原样
  - [ ] 非 SVG 代码块保持完全不变
  - [ ] 大小写变体：svg / SVG / Svg / Svg
  - [ ] 围栏行后有多余空行

  **⚠️ 关键设计细节：SVG 内容必须压缩为单行**

  **为什么需要压缩**：markdown-it 的 HTML 块解析规则中，`<div>` 属于 **Type 1 HTML 块**。CommonMark 规定：Type 1 块的起始标签 `<div>` 开启一个 HTML 块，**遇到空行即终止**。如果 SVG 中有空行，空行后的 SVG 内容会被当作普通 Markdown 解析，导致渲染结果被破坏。

  **修复方案**：将 SVG 内容合并为单行再输出，避免触发空行终止规则：
  ```js
  // 压缩行间空白为单行，防止 markdown-it 因空行截断 HTML 块
  const singleLine = svgLines
    .join('')
    .replace(/>\s+</g, '><')   // <tag> 与 </tag> 间留一个空格
    .replace(/\s{2,}/g, ' ')   // 多余空白合并
    .trim()
  output.push(`<div class="svg-inline-render">${singleLine}</div>`)
  ```

  **伪代码实现**（完整）：
  ```js
  export function renderSvgBlocks(markdown) {
    const lines = markdown.split('\n')
    const output = []
    let i = 0

    while (i < lines.length) {
      const openMatch = lines[i].match(/^( {0,3})(`{3,}|~{3,})\s*(\S*)/)

      if (openMatch && openMatch[3].toLowerCase() === 'svg') {
        const indent = openMatch[1]
        const fenceChar = openMatch[2]
        const openLine = lines[i]
        const svgLines = []
        i++

        // 扫描闭合围栏
        let closed = false
        while (i < lines.length) {
          const closeMatch = lines[i].match(/^( {0,3})(`{3,}|~{3,})\s*$/)
          if (closeMatch
            && closeMatch[1].length <= indent.length   // 缩进 ≤ 开头
            && closeMatch[2][0] === fenceChar[0]       // 同种字符（` 或 ~）
            && closeMatch[2].length >= fenceChar.length) {
            closed = true
            // ⚠️ 压缩为单行，防止 markdown-it HTML 块因空行截断
            const singleLine = svgLines
              .join('')
              .replace(/>\s+</g, '><')
              .replace(/\s{2,}/g, ' ')
              .trim()
            output.push(`<div class="svg-inline-render">${singleLine}</div>`)
            i++
            break
          }
          svgLines.push(lines[i])
          i++
        }

        if (!closed) {
          // 不完整块 — 原样保留（流式安全）
          output.push(openLine)
          output.push(...svgLines)
        }
      } else {
        output.push(lines[i])
        i++
      }
    }

    return output.join('\n')
  }
  ```

  **注意**：本函数只是字符串替换，不负责 XSS 过滤（XSS 由 DOMPurify 在 `renderMarkdown()` 中统一处理）

  **禁止**：
  - 不要修改非 SVG 代码块内的内容
  - 不要添加任何外部依赖
  - 不要在此函数内进行 DOMPurify 处理
  - 不要使用单一大正则 `[\s\S]*?` 直接匹配整个文件（会错误匹配嵌套围栏和内容中的反引号）

  **推荐代理画像**：
  - 类别：`quick` — 单个工具函数，规格清晰
  - 技能：`[]` — 标准 JavaScript 操作（正则 + 字符串处理）
  - 已评估但省略：无

  **并行化**：可并行：是 | 波次 1 | 阻塞：[2] | 依赖：[]

  **参考文件**：
  - `web/src/utils/messageProcessor.js` — 现有工具模块，参考代码风格
  - `web/src/utils/markdown_preview.js` — 本函数将在此文件中被调用

  **验收标准**：
  - [ ] 基本场景：`\`\`\`svg <svg>...</svg> \`\`\`` → `<div class="svg-inline-render"><svg>...</svg></div>`
  - [ ] 反引号围栏：` \`\`\`svg \`\`\` ` → 转换 ✓
  - [ ] 波浪线围栏：` ~~~svg <svg/> ~~~ ` → 转换 ✓
  - [ ] 带缩进围栏：`    \`\`\`svg <svg/> \`\`\`` → 转换 ✓
  - [ ] 不区分大小写：` \`\`\`SVG <svg/> \`\`\`` → 转换 ✓
  - [ ] 不完整块（流式）：`\`\`\`svg <svg>...`（无闭合）→ 保持原样
  - [ ] 非 SVG 代码块：`\`\`\`python print(1) \`\`\`` → 保持原样
   - [ ] 多个连续 SVG 块 → 全部完整转换
   - [ ] SVG 内容包含 HTML 注释等 → 保留内容原样
   - [ ] SVG 内容包含空行 → 压缩为单行，渲染结果正确
   - [ ] 空的 SVG 代码块：`\`\`\`svg\`\`\`` → 安全处理
  - [ ] 导出的函数名为 `renderSvgBlocks`

   **QA 场景**：
   ```
   场景：完整 SVG 块 — 反引号围栏
     工具：Bash
     步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('before\n\`\`\`svg\n<svg><circle/></svg>\n\`\`\`\nafter'));"
     预期：输出包含 'svg-inline-render' 和 '<svg>'，不包含 '\`\`\`svg'
     证据：.sisyphus/evidence/task-1-complete-backtick.txt

   场景：完整 SVG 块 — 波浪线围栏
     工具：Bash
     步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('~~~svg\n<svg><rect/></svg>\n~~~'));"
     预期：输出包含 'svg-inline-render' 和 '<rect/>'
     证据：.sisyphus/evidence/task-1-complete-tilde.txt

   场景：SVG 含空行 — 压缩为单行
     工具：Bash
     步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('\`\`\`svg\n<svg>\n<defs>\n<linearGradient id=\"g\">\n<stop offset=\"0%\"/>\n\n<stop offset=\"100%\"/>\n</linearGradient>\n</defs>\n</svg>\n\`\`\`'));"
     预期：输出仅包含 1 行 '<div class="svg-inline-render">...'
     失败指标：输出包含多个 '<' 开头的行（表明 HTML 块被截断）
     证据：.sisyphus/evidence/task-1-blank-lines.txt

   场景：带缩进的 SVG 块
     工具：Bash
     步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('    \`\`\`svg\n<svg/>\n    \`\`\`'));"
     预期：输出包含 'svg-inline-render'
     证据：.sisyphus/evidence/task-1-indented.txt

  场景：大小写变体 SVG 块
    工具：Bash
    步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('\`\`\`SVG\n<svg/>\n\`\`\`'));"
    预期：输出包含 'svg-inline-render'
    证据：.sisyphus/evidence/task-1-case-insensitive.txt

  场景：不完整 SVG 块（流式）不被转换
    工具：Bash
    步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('before\n\`\`\`svg\n<svg>'));"
    预期：输出包含 '\`\`\`svg'（不变），不包含 'svg-inline-render'
    证据：.sisyphus/evidence/task-1-incomplete.txt

  场景：非 SVG 代码块不受影响
    工具：Bash
    步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('\`\`\`python\\nprint(1)\\n\`\`\`'));"
    预期：输出包含 '\`\`\`python' 和 '\`\`\`'
    证据：.sisyphus/evidence/task-1-python-block.txt

  场景：多个连续 SVG 块
    工具：Bash
    步骤：node -e "const { renderSvgBlocks } = require('./web/src/utils/svgRenderer.js'); console.log(renderSvgBlocks('\`\`\`svg\\n<svg id=\"1\"/>\\n\`\`\`\ntext\n\`\`\`svg\\n<svg id=\"2\"/>\\n\`\`\`'));"
    预期：输出包含 2 个 'svg-inline-render'
    证据：.sisyphus/evidence/task-1-multiple-blocks.txt
  ```

  **提交**：是 | 信息：`feat(web): 添加 SVG 代码块预处理工具函数（行级解析，支持围栏变体）` | 文件：[`web/src/utils/svgRenderer.js`]
  - 提交前命令：`pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js`

---

- [ ] 2. 在 `markdown_preview.js` 中集成 SVG 渲染（无需修改 DOMPurify）

  **任务内容**：修改 `web/src/utils/markdown_preview.js` 中的 `renderMarkdown()` 函数，使其支持 SVG 渲染。

  **关键发现**：经过调研确认，**DOMPurify 的默认配置已经支持 SVG 标签和属性**（见 DOMPurify 源码 `tags.ts` / `attrs.ts`），无需修改其配置。真正的瓶颈在于 Shiki 在 markdown-it 阶段将 ` ```svg ` 代码块渲染为语法高亮的 HTML，导致 SVG 内容以代码形式呈现。因此只需做以下工作：

1. **导入 SVG 预处理函数**：在文件顶部添加 `import { renderSvgBlocks } from './svgRenderer'`

2. **关键：在 `hasCodeFence()` 之前调用 `renderSvgBlocks()`**
   修改后的 `renderMarkdown()` 执行顺序：
   ```
   ① normalizeHtmlTagQuotes()      → 标准化 HTML 引号
   ② renderSvgBlocks()            → 将 ```svg 代码块转为 inline SVG（NEW）
   ③ 生成 cacheKey 基于步骤②产出  → 缓存 key 使用转换后的内容
   ④ 检查缓存 → 命中则直接返回缓存的 HTML
   ⑤ hasCodeFence()               → 检测是否需要语法高亮
   ⑥ collectCodeFenceLanguages()  → 收集需要加载的 Shiki 语言
   ⑦ getRenderer()                → 获取 markdown-it 实例
   ⑧ md.render()                  → Markdown 解析（SVG 已是 raw HTML，pass-through）
   ⑨ DOMPurify.sanitize()         → XSS 过滤（SVG 在默认白名单中）
   ⑩ 缓存结果，返回
   ```
   **为什么转换必须在缓存之前**：
   - 如果先查缓存（基于原始内容），原始内容包含 ` ```svg `，缓存不命中后才转换 → 正确但性能有损
   - 如果先转换再查缓存（基于转换后内容），相同输入直接命中缓存 → 性能更优
   - 且 `hasCodeFence()` 基于转换后内容，**不会把 'svg' 当作代码语言加载 Shiki**，避免了不必要的开销

3. **缓存策略**：cacheKey 应基于 `renderSvgBlocks()` 转换后的内容（`svgContent`），而非原始 `normalizedContent`。因为：
   - 转换前后内容不同，对应的渲染结果不同
   - 用转换后内容做 key 能保证缓存一致性
   - 且避免了先查缓存再转换的"双路径"逻辑

4. **不需要修改 DOMPurify 配置** — 现有 `ADD_TAGS: ['input']` 和 `ADD_ATTR: [...]` 已足够，DOMPurify 默认的 SVG 白名单包含所有常用 SVG 标签和属性，并自动阻止 `<script>`、`onload`、`<foreignObject>`、`<use>` 等危险特性

  **禁止**：
  - 不要修改 Shiki 代码高亮逻辑
  - 不要修改 markdown-it 的其他配置
  - 不要移除或修改现有的 frontmatter、Katex、task lists 插件
  - 不要影响非 SVG 代码块的渲染
  - **不要修改 DOMPurify 的配置**（默认已支持 SVG）

  **推荐代理画像**：
  - 类别：`quick` — 在现有函数中增加预处理步骤
  - 技能：`[]` — 标准 JavaScript 操作
  - 已评估但省略：无

  **并行化**：可并行：是 | 波次 2 | 阻塞：[] | 依赖：[1]

  **参考文件**：
  - `web/src/utils/markdown_preview.js:198-234` — `renderMarkdown()` 函数本体
  - `web/src/utils/markdown_preview.js:203` — 缓存 key 基于 normalizedContent，需在 SVG 预处理后生成
  - `web/src/utils/svgRenderer.js` — 需要导入的预处理函数
  - DOMPurify 源码 `tags.ts` — 确认 SVG 标签白名单（`svg`, `circle`, `rect`, `path`, `g` 等均在默认列表中）
  - DOMPurify 源码 `attrs.ts` — 确认 SVG 属性白名单（`viewBox`, `fill`, `stroke`, `d` 等均在默认列表中）

  **验收标准**：
  - [ ] `renderSvgBlocks` 已导入并在 markdown-it 渲染前调用
  - [ ] **不修改 DOMPurify 配置** — 现有 `ADD_TAGS`/`ADD_ATTR` 保持不变
  - [ ] 包含 ` ```svg` 块的 Markdown 渲染出 SVG（而非代码块）
  - [ ] 不完整的 SVG 块（流式）仍显示为文本代码块
  - [ ] 非 SVG 代码块（python、js 等）不受影响
  - [ ] 现有 frontmatter、Katex、task lists 功能正常

  **QA 场景**：
  ```
  场景：renderMarkdown 将 SVG 代码块渲染为内联 SVG
    工具：Bash（node）
    前置条件：markdown_preview.js 已修改
    步骤：
      1. 运行：node -e "
        const { renderMarkdown } = require('./web/src/utils/markdown_preview.js');
        renderMarkdown('\`\`\`svg\n<svg viewBox=\"0 0 100 50\"><circle cx=\"50\" cy=\"25\" r=\"20\"/></svg>\n\`\`\`', { theme: 'github-light' }).then(console.log);
      "
    预期结果：输出 HTML 中包含 '<svg' 标签，不包含 '\`\`\`svg'
    失败指标：输出中包含 '\`\`\`svg' 或 Shiki 生成的代码高亮 HTML
    证据：.sisyphus/evidence/task-2-render-html.txt

  场景：不完整 SVG 块在流式中保持安全
    工具：Bash（node）
    前置条件：markdown_preview.js 已修改
    步骤：
      1. 运行：node -e "
        const { renderMarkdown } = require('./web/src/utils/markdown_preview.js');
        renderMarkdown('before\n\`\`\`svg\n<svg viewBox=\"0 0 100 50\">', { theme: 'github-light' }).then(console.log);
      "
    预期结果：输出 HTML 中包含 '\`\`\`svg'（作为代码块渲染）
    失败指标：输出中包含 '<svg' 标签
    证据：.sisyphus/evidence/task-2-stream-safe.txt

  场景：聊天消息中 SVG 渲染（集成测试）
    工具：Playwright
    前置条件：应用已运行，可发送聊天消息
    步骤：
      1. 导航到聊天页面
      2. 发送包含 \`\`\`svg 代码块的消息
      3. 等待渲染完成
    预期结果：SVG 渲染为可见图形，而非代码块
    证据：.sisyphus/evidence/task-2-chat-svg.png

  场景：DOMPurify 安全过滤（确认恶意 SVG 被拦截）
    工具：Bash（node）
    前置条件：markdown_preview.js 已修改
    步骤：
      1. 运行：node -e "
        const { renderMarkdown } = require('./web/src/utils/markdown_preview.js');
        // 含 script 标签的恶意 SVG，DOMPurify 应自动拦截
        renderMarkdown('\`\`\`svg\n<svg><script>alert(1)</script></svg>\n\`\`\`', { theme: 'github-light' }).then(console.log);
      "
    预期结果：输出 HTML 中不包含 '<script>' 标签
    失败指标：输出中包含 '<script>alert(1)</script>'
    证据：.sisyphus/evidence/task-2-xss-safe.txt
  ```

  **提交**：是 | 信息：`feat(web): 在 renderMarkdown 中集成 SVG 渲染（DOMPurify 默认已支持 SVG）` | 文件：[`web/src/utils/markdown_preview.js`]
  - 提交前命令：`pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js`

- [ ] 3. 在 `MarkdownPreview.vue` 中添加 SVG 容器 CSS 样式

  **任务内容**：在 `web/src/components/common/MarkdownPreview.vue` 的 `<style>` 中追加 `.svg-inline-render` 类的样式：
  - `max-width: 100%` — 响应式缩放
  - `height: auto` — 保持宽高比
  - `overflow: auto` — 处理超大 SVG 的溢出
  - `margin: 12px 0` — 与周围内容的间距
  - 深色模式：按原样渲染并加上 max-width 约束，为可见性添加半透明背景
  - 将样式放在 `.yk-markdown-preview` 作用域内，避免污染全局样式

  **禁止**：
  - 不要添加 `!important` 标志
  - 不要修改现有的 `.yk-markdown-preview` 样式
  - 不要为深色模式添加基于 JS 的 SVG 操作
  - 不要修改 `src/assets/css/base.css`（全局 SVG 样式只需在 MarkdownPreview 中定义）

  **推荐代理画像**：
  - 类别：`quick` — CSS 追加
  - 技能：[] — 标准 CSS
  - 已评估但省略：无需特殊技能

  **并行化**：可并行：是 | 波次 2 | 阻塞：[] | 依赖：[]

  **参考文件**：
  - `web/src/components/common/MarkdownPreview.vue:53-337` — 现有样式块，包含 .yk-markdown-preview 的所有样式
  - `web/src/components/common/MarkdownPreview.vue:207-215` — 现有 pre.shiki 代码块样式（间距参考）

  **验收标准**：
  - [ ] `.svg-inline-render` 类具有 `max-width: 100%` 和 `height: auto`
  - [ ] SVG 在窄视口下不溢出容器
  - [ ] 深色模式不破坏 SVG 可读性

  **QA 场景**：
  ```
  场景：SVG 响应式缩放
    工具：Playwright
    前置条件：聊天中有已渲染的 SVG
    步骤：
      1. 导航到包含已渲染 SVG 的聊天
      2. 将视口缩放到 375px 宽度（移动端）
      3. 检查 SVG 未溢出容器
    预期结果：SVG 按比例缩小，无水平滚动条
    失败指标：出现水平滚动条或 SVG 被裁剪
    证据：.sisyphus/evidence/task-3-responsive.png

  场景：深色模式下的 SVG
    工具：Playwright
    前置条件：聊天中有已渲染的 SVG
    步骤：
      1. 将主题切换为深色模式
      2. 检查 SVG 仍然可见且可读
    预期结果：SVG 显示清晰，对比度适当
    失败指标：SVG 几乎不可见（与深色背景融合）
    证据：.sisyphus/evidence/task-3-darkmode.png
  ```

  **提交**：是 | 信息：`feat(web): 添加 SVG 响应式容器样式到 MarkdownPreview` | 文件：[`web/src/components/common/MarkdownPreview.vue`]

---

- [ ] 4. 为 svgRenderer.js 添加单元测试

  **任务内容**：使用 Vitest 创建 `web/src/utils/__tests__/svgRenderer.test.js`：
  - 测试完整 SVG 块转换
  - 测试不完整 SVG 块（流式安全）
  - 测试多个 SVG 块
  - 测试非 SVG 代码块不变
  - 测试带有周围 Markdown 内容的 SVG
  - 测试空/格式错误的 SVG 内容
  - 测试 SVG 块在内容的开头/中间/结尾
  - 测试没有 SVG 块（恒等变换）

  **禁止**：
  - 不要测试 Vue 组件行为
  - 不要测试 markdown_preview.js 的渲染行为（那是集成测试范围）

  **推荐代理画像**：
  - 类别：`quick` — 标准 Vitest 单元测试
  - 技能：[] — 标准测试模式
  - 已评估但省略：无需特殊技能

  **并行化**：可并行：是 | 波次 1 | 阻塞：[] | 依赖：[1]

  **参考文件**：
  - `web/src/utils/__tests__/` — 现有测试目录结构
  - `web/src/utils/svgRenderer.js` — 被测函数
  - `web/src/utils/__tests__/` 中其他测试文件 — 测试模式参考

  **验收标准**：
  - [ ] 所有测试用例通过：`pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js`
   - [ ] svgRenderer.js 的 10+ 个测试用例覆盖上述所有场景

  **QA 场景**：
  ```
  场景：所有测试通过
    工具：Bash
    前置条件：svgRenderer.js 和测试文件均已创建
    步骤：
      1. 运行：cd web && pnpm exec vitest run web/src/utils/__tests__/svgRenderer.test.js
    预期结果：所有测试通过（退出码 0）
    失败指标：任何测试失败或退出码非零
    证据：.sisyphus/evidence/task-4-tests-pass.txt
  ```

  **提交**：是 | 信息：`test(web): 为 SVG 渲染工具添加单元测试` | 文件：[`web/src/utils/__tests__/svgRenderer.test.js`]
  - 提交前命令：`pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js`

---

## 最终验证波次（所有实现任务完成后必须执行）

> 4 个审查代理**并行**运行。**全部必须批准**。向用户呈现汇总结果并获取明确的"确认"后才能完成。
>
> **在获得用户明确批准前，不要自动继续执行验证。**
> **在获得用户确认前，永远不要将 F1-F4 标记为已完成。** 如果被拒绝或用户提供反馈，修复 -> 重新运行 -> 再次呈现 -> 等待确认。

- [ ] F1. **计划合规性审计** — `oracle`
  从头到尾阅读计划。对每个"必须包含"：验证实现是否存在（读取文件、curl 端点、运行命令）。对每个"禁止包含"：在代码库中搜索禁止的模式 — 如果发现则以 `文件:行号` 格式拒绝。检查证据文件是否存在于 .sisyphus/evidence/ 中。将交付物与计划进行对比。
  输出：`必须包含 [N/N] | 禁止包含 [N/N] | 任务 [N/N] | 裁决：批准/拒绝`

- [ ] F2. **代码质量审查** — `unspecified-high`
  运行 `tsc --noEmit` + linter + `bun test`。审查所有更改的文件是否存在：`as any`/`@ts-ignore`、空的 catch 块、生产环境中的 console.log、注释掉的代码、未使用的导入。检查 AI 套话：过多的注释、过度抽象、泛型名称（data/result/item/temp）。
  输出：`构建 [通过/失败] | Lint [通过/失败] | 测试 [N通过/N失败] | 文件 [N干净/N有问题] | 裁决`

- [ ] F3. **实际手动 QA** — `unspecified-high`（使用 `playwright` 技能）
  从干净状态开始。执行每个任务中的**每一个** QA 场景 — 遵循确切步骤、捕获证据。测试跨任务集成（功能协同工作，而非孤立测试）。**由于所有渲染路径都通过 MarkdownPreview 入口，需在多个上下文中验证 SVG 渲染**：
  - ✅ **聊天消息中 SVG 渲染**（流式+完成态）：AgentMessageComponent → MarkdownPreview
  - ✅ **子智能体任务结果 SVG 渲染**：TaskTool → MarkdownPreview
  - ✅ **知识库内容 SVG 渲染**：MarkdownContentViewer → MarkdownPreview
  - ✅ **文件预览 SVG 渲染**：AgentFilePreview → MarkdownPreview
  - ✅ **文件详情 SVG 渲染**：FileDetailModal → MarkdownPreview
  - ✅ **不完整 SVG 块（流式场景）**
  - ✅ **非 SVG 代码块不受影响**
   - ✅ **边界情况**：空 SVG 内容、含空行 SVG、格式错误、快速切换主题
  保存至 `.sisyphus/evidence/final-qa/`。
  输出：`场景 [N/N通过] | 组件 [6/6验证] | 边界情况 [N已测试] | 裁决`

- [ ] F4. **范围准确性检查** — `deep`
  对每个任务：阅读"任务内容"，阅读实际差异（git log/diff）。验证 1:1 — 规格中的所有内容都已构建（无缺失），超出规格的内容没有被构建（无膨胀）。检查"禁止包含"合规性。检测跨任务污染：任务 N 触及任务 M 的文件。标记未记录的变更。
  输出：`任务 [N/N合规] | 污染 [干净/N有问题] | 未记录 [干净/N文件] | 裁决`

## 提交策略
- 每个任务独立提交，附带各自的提交信息（见每个任务的提交部分）
- 波次 1 的任务（svgRenderer.js + 测试）可并行提交
- 波次 2 的任务（markdown_preview.js + MarkdownPreview.vue CSS）可并行提交
- 最终验证波次不创建提交

## 成功标准

### 验证命令
```bash
pnpm --filter web exec vitest run web/src/utils/__tests__/svgRenderer.test.js
# 预期：所有测试通过（退出码 0）
```

### 最终检查清单
- [ ] 所有 4 个实现任务 + 4 个验证任务完成
- [ ] ` ```svg` 代码块在所有使用 MarkdownPreview 的组件（6 处）中渲染为内联 SVG
   - [ ] AgentMessageComponent.vue（AI 消息渲染） — ✅
   - [ ] TaskTool.vue（子任务结果渲染） — ✅
   - [ ] MarkdownContentViewer.vue（知识库内容） — ✅
   - [ ] AgentFilePreview.vue（文件预览） — ✅
   - [ ] FileDetailModal.vue（文件详情） — ✅
   - [ ] KbChunkDetailModal.vue（知识块详情） — ✅
- [ ] 流式传输中不完整的 SVG 块安全显示为代码块
- [ ] DOMPurify 默认安全机制生效（脚本、事件处理等被自动拦截）
- [ ] 所有单元测试通过
- [ ] 现有 Markdown 渲染（代码块、表格、Katex、frontmatter 等）无回归
- [ ] 深色模式下 SVG 可见
