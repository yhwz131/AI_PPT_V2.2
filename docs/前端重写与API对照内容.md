# 前端重写与 API 对照

本文说明 **`frontend-new/`**（Vue 3 + Vite + TypeScript）与后端 **`digital_human_interface/`**（FastAPI）之间的路由、接口与数据流对应关系，便于联调与排障。

**部署**：生产环境通常将 **`frontend-new`** 执行 `vite build` 后的产物部署到仓库根目录 **`frontend/`**（与 Nginx 静态根一致）。另一目录 **`new_frontend/`** 为独立前端工程，**不是** 当前文档所述主线；二者勿混淆。详见 [文档索引.md](文档索引.md)。

---

## 1. 技术栈与入口

| 项目 | 说明 |
|------|------|
| 框架 | Vue 3（`<script setup>`） |
| 构建 | Vite |
| 语言 | TypeScript |
| 路由 | `vue-router`，**Hash 模式**（`createWebHashHistory`） |
| HTTP | `fetch`（`src/api/client.ts`） |
| 实时进度 | 自定义 SSE：`fetch` + `ReadableStream`（`src/composables/useSSE.ts`），**未使用**浏览器原生 `EventSource` |

**路由一览**（`src/router/index.ts`）

| 路径 | 页面 | 主要职责 |
|------|------|----------|
| `/` | `IndexPage.vue` | 首页入口：跳转「视频生成」「视频库」 |
| `/upload` | `UploadPage.vue` | PPT 上传 → PDF 预览 → 解说稿 → 选模板/数字人/BGM/情感 → 创建任务 + SSE |
| `/videos` | `VideoListPage.vue` | 从静态 JSON 拉取已生成视频列表并播放 |

---

## 2. 环境变量

| 变量 | 作用 |
|------|------|
| `VITE_API_BASE` | API 与静态资源前缀。开发可设为 `http://127.0.0.1:9088`（与后端端口一致）；**生产若前后端同源部署，常留空**，请求走相对路径。 |

所有 `apiGet` / `apiPost` / `apiUpload` / `apiDelete` 及 `staticUrl()`、`sseUrl()` 均会拼接 `VITE_API_BASE`。

---

## 3. 统一响应格式

后端多数接口返回：

```json
{ "code": 200, "message": "...", "data": { ... } }
```

前端 `ApiResponse<T>` 对应 `code` / `message` / `data`。非 2xx 时从响应体解析 `detail` / `error` / `message` 抛出 `Error`。

---

## 4. 页面 → 模块 → HTTP 对照

### 4.1 首页 `/`

无后端 API，仅导航。页面主文案（`IndexPage.vue`）当前为：英文 `AI PPT Digital Human Presentation Platform`，中文 `AI PPT 数字人讲解平台`；下方两个入口卡片分别为「AI数字人视频生成」「AI数字人视频查看」。

### 4.2 视频库 `/videos`

| 前端 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `fetchVideoList()`（`api/video.ts`） | GET | `/static/data/basic_information.json` | 视频条目列表（`VideoCatalog.data`），带 `?t=` 防缓存 |

后端由 FastAPI 挂载静态目录提供；**不经过**业务 JSON 路由。

### 4.3 生成页 `/upload` — 步骤 0：PPT → PDF

| 前端函数 | 方法 | 路径 | 请求体 | 后端模块 |
|----------|------|------|--------|----------|
| `uploadPPT()` | POST | `/files/preview` | `multipart/form-data`：`file` | `routers/files.py` `preview`：保存文件并后台启动 PDF 转换 |
| `pollConversionTask()` → `getConversionStatus()` | GET | `/conversion/tasks/{task_id}` | — | `routers/conversion.py`：轮询转换状态 |

轮询间隔默认 2s，最多约 90 次；`status === completed` 时 `data` 中含 `pdf_url` / `download_url`（前端用于 `pdfPath` 与 iframe 预览）。

### 4.4 生成页 — 步骤 0：解说稿

| 前端函数 | 方法 | 路径 | 请求体 | 后端说明 |
|----------|------|------|--------|----------|
| `generateScript()` | POST | `/files/voice_over_script_generation` | `file`（PPT）、`pdf_path`、`style` | 口播文案；内部会调 **PaddleOCR 解析服务**（典型 `127.0.0.1:8802`） |

`style` 常用：`brief` / `normal` / `professional`（与 UI「解说风格」一致）。

### 4.5 生成页 — 步骤 1：数字人资源（静态 + 管理）

| 前端函数 | 方法 | 路径 | 说明 |
|----------|------|------|------|
| `fetchDigitalHumans('built-in')` | GET | `/static/Digital_human/Built-in_digital_human.json` | 内置数字人目录 |
| `fetchDigitalHumans('custom')` | GET | `/static/Digital_human/Customized_digital_human.json` | 自定义数字人目录 |
| `uploadCustomDigitalHuman(...)` | POST | `/my_digital_human/digital-human/upload` | `multipart`：`name`、`brief`、`avatar`、`audio`、`video` |
| `deleteDigitalHuman(name)` | DELETE | `/my_digital_human/digital-human/{name}` | 按名称删除自定义数字人 |

对应后端：`routers/my_digital_human.py`（上传/删除）；JSON 由静态文件服务。

### 4.6 生成页 — 步骤 1：背景音乐

| 前端 | 方法 | 路径 | 说明 |
|------|------|------|------|
| `uploadBgm()`（`BgmConfig.vue`） | POST | `/files/upload_bgm` | 返回 `bgm_path`（服务端绝对路径）、`bgm_url`、`file_name` |

生成任务时会把 `bgm_mode` / `bgm_path` 一并 POST 到创建任务接口（见下）。

### 4.6.1 生成页 — 步骤 1：背景欢迎字幕

| 前端 | 说明 |
|------|------|
| `WelcomeTextConfig.vue` | 单行输入「欢迎语」，对应创建任务 JSON 字段 `welcome_text`（可选；留空时后端使用默认欢迎语，并传给 Wav2Lip 等下游） |

步骤 2 确认区会展示「欢迎字幕」摘要（未填写时显示「默认」）。

### 4.7 生成页 — 步骤 2：创建任务 + SSE

| 前端函数 | 方法 | 路径 | 说明 |
|----------|------|------|------|
| `createTask(req)` | POST | `/my_digital_human/tasks` | JSON：`GenerationRequest`（见下） |
| `useSSE().connect(taskId)` | GET | `/my_digital_human/tasks/{task_id}/stream` | **SSE**，`Accept: text/event-stream` |
| `checkTaskExists(taskId)` / `getTaskStatus(taskId)` | GET | `/my_digital_human/task_status/{task_id}` | 刷新恢复任务、判断 404 |

**`GenerationRequest` 主要字段**（与后端 `create_generation_task` 校验一致：`scriptContent`、`human`、`pdf_path` 必填）：

- `scriptContent`：解说稿 HTML 文本  
- `template`：数字人位置，如 `bottom-left`、`top-left`、`none` 等（后端兼容中英文键名）  
- `human`：`name`、`avatar`、`audio`、`video`（静态 URL 路径）  
- `file_name`、`pdf_path`  
- `welcome_text`（可选）  
- `bgm_mode`、`bgm_path`  
- `style`：解说风格  
- `emo_control_method`、`emo_vec`、`emo_text`：情感控制  

**SSE 事件**（与 `routers/my_digital_human.py` 中 `SSEMessage` 一致，前端在 `useSSE` 里解析 `event:` / `data:`）：

- `connected`：连接确认  
- `progress`：阶段进度（含 `stage`、`message`、`progress` 等）  
- `video_result`：单段视频结果（若后端推送）  
- `success`：整体成功（前端取 `hls_info.m3u8_url` / `video_url` / `video_path` 等展示与下载）  
- `error`：错误  
- `end`：流结束  

**任务恢复**：`localStorage` / `sessionStorage` 键 `ppttalk_active_task`；URL 查询参数 `?task=<task_id>`；超过约 24 小时会清除。恢复时先 `checkTaskExists`，再按需 `sseState.connect(taskId)`。

**SSE 断线重连与去重**：服务端将事件写入 `task_event_history` 供重放，并写入队列供当前长连接消费。订阅端 `GET .../stream` 会先重放 history，再读队列；实现上需 **跳过队列中与已重放条数相同的前缀**，否则客户端会收到两遍相同进度日志（详见 [修缮与功能总结.md](修缮与功能总结.md) 6.1.7）。

---

## 5. 新前端当前未直接调用的后端能力（备忘）

以下接口存在于 `digital_human_interface`，**当前 `frontend-new` 未绑定**，便于后续扩展时对照：

| 路径 | 说明 |
|------|------|
| `POST /files/upload` | 仅上传 PPT，不触发预览流水线 |
| `GET /files/{file_id}/info` | 按 `file_id` 查文件 |
| `POST /conversion/start` | 显式启动转换（新前端用 `preview` 已内嵌转换） |
| `POST /my_digital_human/digital_character_generation` | 同步阻塞式生成（旧流程） |
| `POST /my_digital_human/digital_character_generation_stream` | 流式 HTTP（非当前 SSE 任务模型） |
| `GET /my_digital_human/tasks` | 任务列表（管理用） |
| `routers/video.py` 下 `/video/*` | 独立视频处理模块 |

---

## 6. 后端依赖的其他服务（联调视角）

生成链路中，接口服务通常会再请求：

- **IndexTTS**：如 `http://127.0.0.1:6006`（TTS）  
- **Wav2Lip**：如 `http://127.0.0.1:5000`（口型）  
- **PaddleOCR / 解析**：如 `http://127.0.0.1:8802`（PDF 解说稿）  

具体以 `digital_human_interface` 内配置与 `start_all.sh` 为准。

---

## 7. 相关源码索引

| 用途 | 路径 |
|------|------|
| 前端 API 封装 | `frontend-new/src/api/client.ts`、`files.ts`、`conversion.ts`、`digitalHuman.ts`、`video.ts` |
| SSE | `frontend-new/src/composables/useSSE.ts` |
| 上传与生成主流程 | `frontend-new/src/pages/UploadPage.vue` |
| 欢迎字幕 | `frontend-new/src/components/WelcomeTextConfig.vue` |
| 后端路由 | `digital_human_interface/routers/files.py`、`conversion.py`、`my_digital_human.py` |

---

*文档随 `frontend-new` 与 `digital_human_interface` 变更请及时同步。*
