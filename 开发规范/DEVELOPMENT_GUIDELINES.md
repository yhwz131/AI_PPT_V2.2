# PPTTalK 开发规范与流程指南

## 1. 培训目标

- 了解 PPTTalK 项目的整体架构和服务组成
- 掌握项目的开发规范和最佳实践
- 熟悉项目的集成流程和部署方式
- 建立规范的开发习惯和代码质量意识
- 了解如何通过反馈机制持续改进规范

## 2. 项目架构概述

### 2.1 服务组成

| 服务名称 | 端口 | 功能描述 | 技术栈 |
|---------|------|---------|--------|
| PaddleOCR | 8802 | 口播文案识别服务 | Python |
| IndexTTS | 6006 | 语音合成服务 | Python |
| Wav2Lip | 5000 | 唇形同步与视频生成服务 | Python |
| 数字人接口 | 9088 | 数字人总控服务 | Python + FastAPI |
| 前端 | 5173 | 用户界面 | Vue.js |

### 2.2 目录结构

```
PPTTalK/
├── digital_human_interface/   # 数字人接口总控服务
├── wav2lip_workspce/         # Wav2Lip 服务
├── index-tts-vllm/           # IndexTTS 服务
├── paddleocr/                # PaddleOCR 服务
├── frontend-old/             # 旧前端（当前使用）
├── new_frontend(作废)/       # 作废的新前端
├── docs/                     # 项目文档
├── start_all.sh              # 一键启动脚本
├── backend_code_guide.md     # 后端代码规范
├── TESTING_GUIDELINES.md     # 测试规范
└── INTEGRATION_SPEC.md       # 集成规范
```

## 3. 开发规范

### 3.1 后端开发规范

#### 3.1.1 代码风格

- **命名规范**：
  - 目录名：小写字母，单词间用下划线分隔（snake_case）
  - 文件名：小写字母，单词间用下划线分隔（snake_case）
  - 类名：大驼峰命名法（CamelCase）
  - 函数名：小写字母，单词间用下划线分隔（snake_case）
  - 变量名：小写字母，单词间用下划线分隔（snake_case）
  - 常量名：全大写字母，单词间用下划线分隔（SNAKE_CASE）

- **代码格式**：
  - 缩进：使用4个空格
  - 行宽：每行不超过100个字符
  - 空行：类与类之间空2行，函数与函数之间空2行，函数内部逻辑块之间空1行
  - 括号：函数定义和调用时，括号内不加空格；列表、字典、元组等括号内，元素之间加空格

- **注释规范**：
  - 模块级注释：每个模块顶部添加模块描述
  - 函数注释：使用文档字符串（docstring）描述函数功能、参数、返回值
  - 行注释：使用 `#` 注释，解释复杂逻辑
  - TODO注释：使用 `# TODO:` 标记待完成的任务

#### 3.1.2 API 设计规范

- **路由设计**：
  - 路由路径：使用小写字母，单词间用连字符（-）分隔
  - HTTP方法：
    - `GET`：获取资源
    - `POST`：创建资源
    - `PUT`：更新资源
    - `DELETE`：删除资源
  - 路径参数：使用 `{parameter}` 格式
  - 查询参数：使用 `Query` 装饰器
  - 请求体：使用 Pydantic 模型

- **响应格式**：
  - 成功响应：
    ```json
    {
      "status": "success",
      "message": "操作成功",
      "data": {...}
    }
    ```
  - 错误响应：
    ```json
    {
      "status": "error",
      "message": "错误信息",
      "detail": "详细错误信息"
    }
    ```

- **状态码**：
  - `200 OK`：请求成功
  - `201 Created`：资源创建成功
  - `204 No Content`：无内容
  - `400 Bad Request`：请求参数错误
  - `401 Unauthorized`：未授权
  - `403 Forbidden`：禁止访问
  - `404 Not Found`：资源不存在
  - `500 Internal Server Error`：服务器内部错误

#### 3.1.3 异常处理

- 使用 `HTTPException` 抛出 HTTP 异常
- 实现全局异常处理器
- 记录异常日志

#### 3.1.4 日志规范

- 使用 Python 标准库 `logging`
- 日志级别：
  - `DEBUG`：调试信息
  - `INFO`：一般信息
  - `WARNING`：警告信息
  - `ERROR`：错误信息
  - `CRITICAL`：严重错误
- 日志格式：包含时间、级别、模块名、消息

#### 3.1.5 依赖注入

- 使用 FastAPI 的 `Depends` 机制
- 实现服务层的依赖注入
- 避免循环依赖

### 3.2 前端开发规范

#### 3.2.1 代码风格

- **命名规范**：
  - 组件名：大驼峰命名法（CamelCase）
  - 变量名：小驼峰命名法（camelCase）
  - 常量名：全大写，单词间用下划线分隔（SNAKE_CASE）

- **代码格式**：
  - 使用 Prettier 格式化代码
  - 保持代码风格的一致性

- **类型安全**：
  - 使用 TypeScript
  - 明确类型定义

#### 3.2.2 API 调用规范

- **API 客户端**：
  - 使用 `apiGet`、`apiPost`、`apiUpload`、`apiDelete` 函数
  - 统一错误处理

- **环境配置**：
  - 通过 `.env` 文件配置 API 基础 URL
  - 支持不同环境的配置

- **错误处理**：
  - 统一错误处理逻辑
  - 提供友好的错误提示

## 4. 开发流程

### 4.1 新功能开发流程

1. **需求分析与规划**
   - 明确新功能的业务需求和技术要求
   - 确定新功能与现有系统的集成点
   - 评估集成风险和影响范围

2. **设计阶段**
   - 设计新功能的接口规范
   - 设计数据模型和流程
   - 确定与现有系统的交互方式

3. **开发阶段**
   - 实现新功能代码
   - 遵循项目的代码规范
   - 确保与现有系统的兼容性

4. **测试阶段**
   - 编写单元测试和集成测试
   - 进行端到端测试
   - 验证新功能与现有系统的集成效果

5. **部署阶段**
   - 更新部署脚本和配置
   - 部署新功能到测试环境
   - 验证部署效果

6. **上线阶段**
   - 部署新功能到生产环境
   - 监控系统运行状态
   - 收集用户反馈

### 4.2 服务集成流程

1. **服务注册**
   - 在 `start_all.sh` 中注册新服务
   - 配置服务的环境、端口、工作目录等信息

2. **服务启动**
   - 确保服务按正确的顺序启动
   - 实现服务健康检查机制

3. **服务通信**
   - 定义服务间的通信协议
   - 实现服务间的调用逻辑

4. **服务监控**
   - 集成到现有的监控系统
   - 实现服务状态的实时监控

## 5. 测试规范

### 5.1 测试类型

#### 5.1.1 单元测试

- **前端单元测试**：
  - 框架: Vitest
  - 测试范围: 组件功能测试、工具函数测试、状态管理测试、路由测试

- **后端单元测试**：
  - 框架: pytest
  - 测试范围: 核心功能模块测试、工具函数测试、API 接口测试、模型加载和推理测试

#### 5.1.2 集成测试

- **前端集成测试**：
  - 框架: Vitest + Testing Library
  - 测试范围: 组件间交互测试、页面导航测试、表单提交测试、API 调用测试

- **后端集成测试**：
  - 框架: pytest + FastAPI TestClient
  - 测试范围: 模块间集成测试、API 与业务逻辑集成测试、数据库操作测试

#### 5.1.3 端到端测试

- **框架**: Playwright
- **测试范围**: 完整用户流程测试、跨浏览器兼容性测试、响应式布局测试、性能测试

### 5.2 测试覆盖率目标

- **前端测试覆盖率**：
  - 整体覆盖率: ≥ 80%
  - 关键功能覆盖率: ≥ 90%
  - 组件测试覆盖率: ≥ 85%
  - 工具函数覆盖率: ≥ 95%

- **后端测试覆盖率**：
  - 整体覆盖率: ≥ 75%
  - 核心功能覆盖率: ≥ 90%
  - API 接口覆盖率: ≥ 85%
  - 工具函数覆盖率: ≥ 90%

### 5.3 测试执行机制

- **本地测试**：
  - 前端测试: `npm test`
  - 后端测试: `pytest`
  - 端到端测试: `npm run test:e2e`

- **CI/CD 测试**：
  - 集成测试: 每次提交时执行
  - 端到端测试: 每次合并到主分支时执行
  - 覆盖率检查: 每次提交时执行，低于目标值则失败

## 6. 部署规范

### 6.1 服务部署

1. **环境配置**
   - 使用环境变量配置服务
   - 提供配置模板

2. **启动脚本**
   - 更新 `start_all.sh` 脚本
   - 确保服务的正确启动顺序

3. **监控配置**
   - 集成到监控系统
   - 配置告警机制

### 6.2 版本管理

1. **版本控制**
   - 使用 Git 进行版本控制
   - 遵循 Git 工作流

2. **发布流程**
   - 制定发布计划
   - 执行发布流程
   - 监控发布效果

## 7. 代码示例

### 7.1 后端 API 示例

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

@app.post("/items/")
def create_item(item: Item):
    """创建新物品"""
    return {"status": "success", "message": "物品创建成功", "data": item}

@app.get("/items/{item_id}")
def read_item(item_id: int):
    """获取物品信息"""
    if item_id not in items:
        raise HTTPException(status_code=404, detail="物品不存在")
    return {"status": "success", "message": "获取成功", "data": items[item_id]}
```

### 7.2 前端 API 调用示例

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000,
});

export const apiGet = async (url: string, params?: any) => {
  try {
    const response = await apiClient.get(url, { params });
    return response.data;
  } catch (error) {
    handleApiError(error);
    throw error;
  }
};

export const apiPost = async (url: string, data?: any) => {
  try {
    const response = await apiClient.post(url, data);
    return response.data;
  } catch (error) {
    handleApiError(error);
    throw error;
  }
};

const handleApiError = (error: any) => {
  if (error.response) {
    console.error('API Error:', error.response.data);
  } else if (error.request) {
    console.error('API Error: No response received');
  } else {
    console.error('API Error:', error.message);
  }
};
```

### 7.3 测试示例

```python
# 后端测试示例
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_item():
    response = client.post("/items/", json={"name": "Test Item", "price": 10.99})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["data"]["name"] == "Test Item"

def test_read_item():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
```

## 8. 反馈机制

### 8.1 代码审查

- 定期进行代码审查
- 使用代码审查工具
- 检查代码质量
- 确保代码符合规范

### 8.2 反馈收集

- **问题反馈**：
  - 使用 GitLab/GitHub Issues 跟踪问题
  - 定期回顾和解决问题

- **改进建议**：
  - 建立规范改进建议渠道
  - 定期讨论和评估建议

- **培训反馈**：
  - 收集培训效果反馈
  - 持续优化培训内容

### 8.3 持续改进

- **规范更新**：
  - 定期更新开发规范
  - 确保规范与项目发展同步

- **工具优化**：
  - 引入新的开发工具
  - 优化现有工具配置

- **流程改进**：
  - 分析开发流程中的瓶颈
  - 持续优化开发流程

## 9. 培训计划

### 9.1 培训内容

1. **项目架构介绍**
   - 服务组成和功能
   - 目录结构和代码组织

2. **开发规范培训**
   - 后端代码规范
   - 前端代码规范
   - API 设计规范

3. **开发流程培训**
   - 新功能开发流程
   - 服务集成流程
   - 测试流程

4. **部署与监控**
   - 服务部署方法
   - 监控系统使用
   - 故障排查

5. **最佳实践分享**
   - 代码质量提升
   - 性能优化技巧
   - 安全最佳实践

### 9.2 培训方式

- **理论讲解**：通过文档和演示讲解规范和流程
- **实践操作**：通过实际案例练习规范的应用
- **代码审查**：通过代码审查实践学习规范的应用
- **讨论交流**：通过讨论解决实际问题和分享经验

### 9.3 培训评估

- **知识测试**：通过测试了解培训效果
- **实践评估**：通过实际项目评估规范的应用情况
- **反馈收集**：收集培训反馈，持续改进培训内容

## 10. 结论

本指南旨在为 PPTTalK 项目团队提供完整的开发规范和流程指导，帮助团队成员了解和遵循项目的开发标准，提高代码质量和开发效率。通过建立规范的开发流程和反馈机制，我们可以持续改进项目的质量和可维护性，确保项目的长期稳定发展。

所有团队成员都应该认真学习和遵循本指南中的规范和流程，共同维护 PPTTalK 项目的代码质量和开发标准。