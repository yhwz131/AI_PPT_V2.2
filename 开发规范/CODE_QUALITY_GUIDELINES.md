# PPTTalK 代码质量检查标准与流程

## 1. 代码质量检查工具

### 1.1 前端工具
- **ESLint**: 用于检查 JavaScript/TypeScript 代码的语法错误和代码风格问题
- **Prettier**: 用于统一代码格式化
- **TypeScript**: 用于类型检查

### 1.2 后端工具
- **Black**: 用于 Python 代码格式化
- **Flake8**: 用于检查 Python 代码的语法错误和代码风格问题
- **Pylint**: 用于更全面的 Python 代码质量检查

## 2. 代码质量检查标准

### 2.1 前端代码标准
- 使用 TypeScript 进行类型检查
- 遵循 ESLint 配置中的规则，包括命名规范、代码风格等
- 使用 Prettier 统一代码格式化
- 组件命名使用 PascalCase
- 变量命名使用 camelCase 或 UPPER_CASE
- 函数命名使用 camelCase
- 接口和类型别名使用 PascalCase
- 代码缩进使用 2 个空格
- 字符串使用单引号
- 每行代码长度不超过 80 个字符
- 大括号使用空格包围
- 箭头函数参数始终使用括号
- 行尾使用 LF 换行符

### 2.2 后端代码标准
- 使用 Black 进行代码格式化
- 遵循 Flake8 配置中的规则
- 遵循 Pylint 配置中的规则
- 每行代码长度不超过 100 个字符
- 代码缩进使用 4 个空格
- 函数参数不超过 10 个
- 局部变量不超过 15 个
- 返回值不超过 6 个
- 分支不超过 12 个
- 语句不超过 50 个

## 3. 代码质量检查流程

### 3.1 本地开发流程
1. **前端开发**:
   - 运行 `npm run lint` 检查代码质量
   - 运行 `npm run format` 格式化代码
   - 运行 `npx vue-tsc --noEmit` 进行类型检查

2. **后端开发**:
   - 运行 `black .` 格式化代码
   - 运行 `flake8 .` 检查代码质量
   - 运行 `pylint $(find . -name "*.py" -type f | grep -v __pycache__)` 进行更全面的代码质量检查

### 3.2 CI/CD 流程
- 当代码推送到 `main` 或 `develop` 分支时，自动运行代码质量检查
- 当创建或更新 Pull Request 时，自动运行代码质量检查
- 代码质量检查失败的提交或 Pull Request 将被拒绝合并

## 4. 工具配置文件

### 4.1 前端配置文件
- `.eslintrc.cjs`: ESLint 配置
- `.prettierrc`: Prettier 配置
- `.prettierignore`: Prettier 忽略文件
- `tsconfig.json`: TypeScript 配置

### 4.2 后端配置文件
- `pyproject.toml`: Black 配置
- `.flake8`: Flake8 配置
- `.pylintrc`: Pylint 配置

## 5. 常见问题与解决方案

### 5.1 ESLint 错误
- **问题**: 未使用的变量
  **解决方案**: 删除未使用的变量或使用 `// eslint-disable-next-line` 注释

- **问题**: 代码风格不符合规范
  **解决方案**: 运行 `npm run format` 自动格式化代码

### 5.2 TypeScript 错误
- **问题**: 类型不匹配
  **解决方案**: 检查变量类型并正确定义类型

### 5.3 Python 代码质量问题
- **问题**: 代码格式化不符合规范
  **解决方案**: 运行 `black .` 自动格式化代码

- **问题**: 代码风格不符合规范
  **解决方案**: 根据 Flake8 和 Pylint 的提示进行修改

## 6. 最佳实践

- 在提交代码前，确保所有代码质量检查都通过
- 使用 IDE 的 ESLint 和 Prettier 插件，实时检查代码质量
- 定期运行代码质量检查工具，确保代码质量
- 团队成员之间定期交流代码质量问题，共同提高代码质量

## 7. 结论

代码质量是项目成功的关键因素之一。通过使用 ESLint、Prettier、Black、Flake8 和 Pylint 等工具，我们可以确保代码的一致性、可读性和可维护性。同时，通过将这些工具集成到 CI/CD 流程中，我们可以自动检查代码质量，确保只有符合标准的代码才能合并到主分支。

希望团队成员能够严格遵循这些代码质量标准和流程，共同维护一个高质量的代码库。