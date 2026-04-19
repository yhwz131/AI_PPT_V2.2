# digital_human_interface 管理控制台（9088 `/console`）

本文说明 **`digital_human_interface`**（默认 **9088** 端口）自带的 **Web 管理控制台**：访问方式、界面分区、与后端接口的对应关系，以及运维与安全注意点。可与 [`jnadigital_human_data_flow.md`](jnadigital_human_data_flow.md)、[`jnaaippt_architecture_v1.md`](jnaaippt_architecture_v1.md) 对照阅读。

---

## 一、文档范围内「有没有写过」

- 现有文档里 **多次出现 9088 端口**（架构、数据流、前端 API 说明等），但 **没有单独成章** 介绍 `/console` 页面本身。
- **本文件** 专门描述该控制台；实现代码位于 `digital_human_interface/templates/index.html` 与 `digital_human_interface/static/js/app.js`，路由与 API 在 `digital_human_interface/main.py`。

---

## 二、访问入口与相关 URL

服务启动后（见 `main.py` 启动日志），典型地址为：

| 路径 | 说明 |
|------|------|
| `http://<HOST>:<PORT>/` | JSON：服务名、状态、指向 `/console` 与 `/docs` 的提示 |
| `http://<HOST>:<PORT>/console` | **管理控制台**（本页文档主题） |
| `http://<HOST>:<PORT>/docs` | Swagger UI（OpenAPI 文档） |

`<PORT>` 默认 **9088**，以 `config` / 环境变量中的 `PORT` 为准。

---

## 三、页面结构概览

控制台为 **单页应用式布局**：先 **登录**，通过后显示顶栏、Tab 导航与底部状态栏。

### 3.1 登录与鉴权

- 登录请求：`POST /api/admin/login`，JSON 体为 `username`、`password`。
- 成功后返回 `token`；前端存入 `sessionStorage`（键 `admin_token`），后续需管理员权限的请求带请求头 **`X-Admin-Token: <token>`**。
- **账号与口令** 在 `main.py` 中定义为 `ADMIN_USERNAME`、`ADMIN_PASSWORD`。**生产环境必须修改**，并限制仅内网或 VPN 可达；勿将默认口令写入对外文档或截图。

### 3.2 五个 Tab

| Tab | 名称 | 主要职责 |
|-----|------|----------|
| 1 | 仪表盘 | CPU / 内存 / 磁盘、GPU（最多展示前 2 块卡）、各微服务端口连通性、WebSocket 连接统计 |
| 2 | 实时控制台 | 通过 **WebSocket** 接收实时日志；支持筛选、暂停、导出；底部可输入简单命令 |
| 3 | 日志文件 | 按服务切换查看 **磁盘上的日志文件尾部**（需登录） |
| 4 | 视频管理 | 读取 `static/data/basic_information.json` 中的视频列表，支持按条删除及关联文件清理（需登录） |

**视频删除范围（与「不删」）**：删除的是 JSON 中 **指定 index 的一条记录**，并在 `digital_human_interface` 下尽量删除该条对应的 PDF、合并视频、HLS 目录、`static/file/images/<uuid>` 等路径；**仍被其它记录引用的路径会保留**。**不会**删除 Wav2Lip 服务目录（如 `wav2lip_workspce/.../image_output/`）中的单页中间文件，详见 [各服务配置与常见问题说明.md](各服务配置与常见问题说明.md) 中 Wav2Lip 小节。
| 5 | 系统控制 | 同步执行文件清理、查看定时任务、调整日志级别、发送测试日志 |

---

## 四、前端调用的主要 HTTP 接口

以下路径均相对 **`digital_human_interface` 根 URL**（例如 `http://127.0.0.1:9088`）。**是否需 `X-Admin-Token`** 已标注。

### 4.1 公开或弱鉴权（用于仪表盘 / 调试）

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/system/info` | CPU、内存、磁盘等（`psutil`） |
| GET | `/api/system/gpu` | GPU 信息（`nvidia-smi`；无驱动或未安装时返回错误态） |
| GET | `/api/system/services` | 探测本机 **8802 / 6006 / 5000 / 9088** 端口是否可连接 |
| GET | `/api/connections` | WebSocket 连接统计 |
| GET | `/api/logs/recent?limit=` | 主日志文件尾部若干行（控制台初次加载历史） |
| POST | `/api/commands/test-log` | 写入测试日志（JSON：`message`、`level`） |
| GET | `/api/cleanup/run-sync` | **同步**执行清理任务并返回结果（系统控制 Tab） |
| GET | `/api/scheduler/jobs` | 列出定时任务 |
| GET | `/api/logs/level` | 当前各 logger/handler 级别 |
| POST | `/api/logs/level/{level_name}` | 设置日志级别；服务端校验为 **INFO / WARNING / ERROR / CRITICAL**（见下文说明） |

### 4.2 需管理员 Token

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/admin/login` | 登录并获取 token |
| GET | `/api/admin/logs/{service_name}` | 读取指定服务日志尾部；`service_name` 为 `digital`、`tts`、`wav2lip`、`paddleocr`、`cleanup` |
| POST | `/api/admin/services/{action}` | `action` ∈ `start` / `stop` / `restart`；body JSON：`{"service":"paddleocr|tts|wav2lip|digital"}`。**DigitalHuman（digital）仅允许 `restart`**，且通过 `start_all.sh` 执行 |
| GET | `/api/admin/videos` | 视频列表（带 `_index`） |
| POST | `/api/admin/videos/delete` | 按 `index` 删除一条记录，可选带 `pdf_path`、`file_name` 做并发校验 |

另有异步清理 `GET /api/cleanup/run`、调度器 `pause` / `resume` / `delete` 等接口在 `main.py` 中定义；当前控制台 **主要使用** `run-sync` 与任务列表查询，其余以实际页面按钮为准。

---

## 五、WebSocket（`/ws`）

- 浏览器使用 **`ws://<host>:<port>/ws`**（HTTPS 页面则为 `wss://`）。
- **心跳**：前端约每 30s 发送 `{"type":"ping"}`，服务端回复 `pong`。
- **日志推送**：服务端通过自定义 `WebSocketLogHandler` 将日志推给前端，消息类型含 `log`（实时控制台展示）。
- **命令**：前端发送 `{"type":"command","command":"..."}`；`main.py` 中示例为 `get_stats`，返回 CPU/内存/连接等。**控制台输入框** 内置 `help` / `clear` / `stats`（`stats` 走上述 command 分支）。

断线后会按次数递增延迟尝试重连（最多约 10 次）。

---

## 六、与业务 API 的关系

- **`/console` 面向运维与监控**，与 **PPT 上传、数字人生成、SSE 任务流** 等业务路由（如 `/files/*`、`/my_digital_human/*`）**相互独立**。
- **视频管理** Tab 操作的 **`basic_information.json`** 与前端「视频库」读取的 **是同一份数据**；在控制台删除记录会同步删文件并更新 JSON，请谨慎操作。

---

## 七、运维与安全建议

1. **改默认管理员密码**，并配合防火墙 / 反向代理仅开放给可信网络。  
2. **重启 DigitalHuman**：控制台通过 `start_all.sh restart digital` 触发 detached 重启，**当前连接会断开**，页面约 10 秒后自动刷新。  
3. **微服务启停**：依赖仓库根目录 `start_all.sh` 存在且可执行；无 GPU 时仪表盘 GPU 区域可能为空或报错，属预期。  
4. **日志级别 UI**：页面下拉框含 `DEBUG` 等选项时，若后端 `POST /api/logs/level/{level_name}` **不接受**该级别，会返回 400；以 `main.py` 中 `set_log_level` 的允许列表为准。  
5. 经 **Nginx** 反代时，需为 **`/ws`** 配置 WebSocket 升级，**`/console`** 静态资源与 API 同域可避免跨域问题。

---

## 八、源码索引

| 内容 | 路径 |
|------|------|
| 页面 HTML | `digital_human_interface/templates/index.html` |
| 前端逻辑 | `digital_human_interface/static/js/app.js` |
| 样式 | `digital_human_interface/static/css/style.css` |
| 路由与全部 `/api/*`、`/ws` | `digital_human_interface/main.py` |

---

*若控制台功能或接口有变更，请同步更新本文与 `main.py` 注释。*
