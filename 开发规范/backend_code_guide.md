# PPTTalK 后端代码规范

## 1. 项目结构

### 1.1 目录结构

```
digital_human_interface/
├── main.py                    # 应用主入口
├── routers/                   # 路由模块
│   ├── __init__.py
│   ├── files.py               # 文件管理路由
│   ├── conversion.py          # 转换服务路由
│   ├── my_digital_human.py    # 数字人相关路由
│   ├── video.py               # 视频相关路由
│   └── sse_monitor.py         # SSE监控中间件
├── services/                  # 服务层
│   ├── __init__.py
│   ├── cleanup_service.py     # 文件清理服务
│   ├── conversion_service.py  # 转换服务
│   ├── file_service.py        # 文件服务
│   ├── json_info_service.py   # JSON数据管理服务
│   ├── pdf_image_service.py   # PDF转图片服务
│   ├── scheduler_service.py   # 定时任务调度服务
│   └── video_merge_service.py # 视频合并服务
├── core/                      # 核心功能
│   ├── __init__.py
│   ├── converter.py           # 转换核心逻辑
│   ├── dependencies.py        # 依赖注入
│   └── libreoffice_converter.py # LibreOffice转换器
├── config/                    # 配置管理
│   ├── __init__.py
│   ├── config.py              # 配置验证
│   └── settings.py            # 应用设置
├── static/                    # 静态文件
├── templates/                 # 模板文件
├── logs/                      # 日志文件
└── requirements.txt           # 依赖文件
```

### 1.2 模块命名

- **目录名**：使用小写字母，单词间用下划线分隔（snake_case）
- **文件名**：使用小写字母，单词间用下划线分隔（snake_case）
- **模块名**：与文件名保持一致

## 2. 代码风格

### 2.1 命名规范

- **类名**：使用大驼峰命名法（CamelCase）
- **函数名**：使用小写字母，单词间用下划线分隔（snake_case）
- **变量名**：使用小写字母，单词间用下划线分隔（snake_case）
- **常量名**：使用全大写字母，单词间用下划线分隔（SNAKE_CASE）
- **参数名**：使用小写字母，单词间用下划线分隔（snake_case）
- **返回值**：使用描述性的变量名

### 2.2 代码格式

- **缩进**：使用4个空格
- **行宽**：每行不超过100个字符
- **空行**：
  - 类与类之间空2行
  - 函数与函数之间空2行
  - 函数内部逻辑块之间空1行
- **括号**：
  - 函数定义和调用时，括号内不加空格
  - 列表、字典、元组等括号内，元素之间加空格

### 2.3 注释规范

- **模块级注释**：每个模块顶部添加模块描述
- **函数注释**：使用文档字符串（docstring）描述函数功能、参数、返回值
- **行注释**：使用 `#` 注释，解释复杂逻辑
- **TODO注释**：使用 `# TODO:` 标记待完成的任务

## 3. API 设计规范

### 3.1 路由设计

- **路由路径**：使用小写字母，单词间用连字符（-）分隔
- **HTTP方法**：
  - `GET`：获取资源
  - `POST`：创建资源
  - `PUT`：更新资源
  - `DELETE`：删除资源
- **路径参数**：使用 `{parameter}` 格式
- **查询参数**：使用 `Query` 装饰器
- **请求体**：使用 Pydantic 模型

### 3.2 响应格式

- **成功响应**：
  ```json
  {
    "status": "success",
    "message": "操作成功",
    "data": {...}
  }
  ```
- **错误响应**：
  ```json
  {
    "status": "error",
    "message": "错误信息",
    "detail": "详细错误信息"
  }
  ```

### 3.3 状态码

- `200 OK`：请求成功
- `201 Created`：资源创建成功
- `204 No Content`：无内容
- `400 Bad Request`：请求参数错误
- `401 Unauthorized`：未授权
- `403 Forbidden`：禁止访问
- `404 Not Found`：资源不存在
- `500 Internal Server Error`：服务器内部错误

## 4. 异常处理

- 使用 `HTTPException` 抛出 HTTP 异常
- 实现全局异常处理器
- 记录异常日志

## 5. 日志规范

- 使用 Python 标准库 `logging`
- 日志级别：
  - `DEBUG`：调试信息
  - `INFO`：一般信息
  - `WARNING`：警告信息
  - `ERROR`：错误信息
  - `CRITICAL`：严重错误
- 日志格式：包含时间、级别、模块名、消息

## 6. 依赖注入

- 使用 FastAPI 的 `Depends` 机制
- 实现服务层的依赖注入
- 避免循环依赖

## 7. 安全规范

- 使用 HTTPS
- 实现 CORS 配置
- 敏感信息使用环境变量
- 密码加密存储
- 防止 SQL 注入
- 防止 XSS 攻击

## 8. 性能优化

- 使用异步编程
- 合理使用缓存
- 数据库查询优化
- 避免重复计算
- 合理使用背景任务

## 9. 测试规范

- 编写单元测试
- 编写集成测试
- 测试覆盖率目标：80%以上
- 使用 `pytest` 框架

## 10. 部署规范

- 使用 Docker 容器
- 配置环境变量
- 实现健康检查
- 配置日志轮转
- 监控系统资源使用

## 11. 工具配置

### 11.1 Pylint 配置

创建 `.pylintrc` 文件：

```ini
[MASTER]
disable=missing-docstring,bad-continuation
max-line-length=100

[MESSAGES CONTROL]
disable=C0111,C0330

[FORMAT]
max-line-length=100
indent-string='    '

[DESIGN]
max-args=10
max-locals=15
max-returns=6
max-branches=12
max-statements=50
```

### 11.2 Flake8 配置

创建 `.flake8` 文件：

```ini
[flake8]
max-line-length = 100
exclude = .git,__pycache__,build,dist
ignore = E501,W503
```

### 11.3 Black 配置

创建 `pyproject.toml` 文件：

```toml
[tool.black]
line-length = 100
target-version = ['py39']
include = '\.pyi?$'
extend-exclude = '''/(\n    \.git
    | __pycache__
    | build
    | dist
)/'''
```

## 12. 代码审查

- 定期进行代码审查
- 使用代码审查工具
- 检查代码质量
- 确保代码符合规范

## 13. 版本控制

- 使用 Git
- 遵循 Git 工作流
- 提交信息规范：
  ```
  <type>: <description>
  
  <body>
  
  <footer>
  ```
  其中 type 包括：feat、fix、docs、style、refactor、test、chore

## 14. 文档

- 编写 API 文档
- 编写部署文档
- 编写开发文档
- 使用 Swagger UI 或 ReDoc

## 15. 最佳实践

- 遵循 SOLID 原则
- 遵循 DRY 原则
- 代码可读性优先
- 安全性优先
- 性能优化
- 可维护性

---

本规范适用于 PPTTalK 项目的后端开发，所有开发人员应严格遵守。