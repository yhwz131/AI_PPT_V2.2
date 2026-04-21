# PPTTalK 前端代码规范

## 1. 命名规范

### 1.1 组件命名
- 组件名称使用 PascalCase 格式（大驼峰命名法）
- 组件文件名与组件名称保持一致
- 文件夹名使用 kebab-case 格式（短横线命名法）

**示例：**
```
components/
  Button/
    Button.vue
  UserProfile/
    UserProfile.vue
```

### 1.2 变量命名
- 普通变量使用 camelCase 格式（小驼峰命名法）
- 常量使用 UPPER_CASE 格式（全大写，下划线分隔）
- 私有变量使用 _ 前缀

**示例：**
```typescript
const userName = 'John';
const MAX_COUNT = 100;
const _privateVar = 'private';
```

### 1.3 函数命名
- 函数名使用 camelCase 格式（小驼峰命名法）
- 函数名应清晰表达其功能
- 回调函数可以使用 on 前缀

**示例：**
```typescript
function getUserInfo() {}
function onSubmit() {}
```

### 1.4 接口和类型命名
- 接口名称使用 PascalCase 格式，并以 I 前缀
- 类型别名使用 PascalCase 格式

**示例：**
```typescript
interface IUser {
  id: number;
  name: string;
}

type UserList = IUser[];
```

### 1.5 文件命名
- 组件文件：PascalCase.vue
- 工具文件：camelCase.ts
- 类型文件：types.ts 或 PascalCase.ts
- 样式文件：kebab-case.scss 或 kebab-case.css

## 2. 文件结构

```
src/
├── assets/           # 静态资源
│   ├── images/       # 图片
│   ├── styles/       # 全局样式
│   └── fonts/        # 字体
├── components/       # 通用组件
│   ├── Button/       # 组件文件夹
│   ├── Input/        # 组件文件夹
│   └── ...
├── composables/      # 组合式函数
├── pages/            # 页面组件
│   ├── Home/         # 页面文件夹
│   ├── About/        # 页面文件夹
│   └── ...
├── router/           # 路由配置
├── api/              # API 调用
├── utils/            # 工具函数
├── types/            # TypeScript 类型定义
├── store/            # 状态管理（如果使用 Pinia 或 Vuex）
├── App.vue           # 根组件
└── main.ts           # 入口文件
```

## 3. 代码风格

### 3.1 缩进和换行
- 使用 2 个空格进行缩进
- 每行代码长度不超过 80 个字符
- 大括号使用独立行
- 逗号后添加空格

**示例：**
```typescript
if (condition) {
  // 代码
} else {
  // 代码
}

const user = {
  id: 1,
  name: 'John'
};
```

### 3.2 空格
- 操作符前后添加空格
- 函数参数之间添加空格
- 括号内不添加空格
- 逗号后添加空格

**示例：**
```typescript
const result = a + b;
function getUser(id, name) {}
const arr = [1, 2, 3];
```

### 3.3 注释
- 组件应添加 JSDoc 注释
- 复杂逻辑应添加行内注释
- 注释应清晰、简洁，避免冗余

**示例：**
```typescript
/**
 * 用户组件
 * @param {string} name - 用户名
 * @param {number} age - 年龄
 */
function User({ name, age }) {
  // 计算用户是否成年
  const isAdult = age >= 18;
  return <div>{name} ({isAdult ? '成年' : '未成年'})</div>;
}
```

### 3.4 Vue 组件风格
- 使用 Script Setup 语法
- 组件属性使用 kebab-case
- 模板中使用单引号
- 自闭合标签

**示例：**
```vue
<template>
  <div class="user-profile">
    <h2>{{ userName }}</h2>
    <Button type="primary" @click="handleClick" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  userName: string;
}>();

const emit = defineEmits<{
  (e: 'click'): void;
}>();

function handleClick() {
  emit('click');
}
</script>

<style scoped>
.user-profile {
  padding: 16px;
}
</style>
```

## 4. 组件设计规范

### 4.1 组件职责
- 组件应保持单一职责
- 组件应可复用
- 组件应易于测试

### 4.2 Props 设计
- Props 应使用 TypeScript 类型定义
- Props 应添加默认值
- Props 应添加验证（如果需要）

**示例：**
```typescript
defineProps<{
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
}>();

// 或使用 withDefaults
defineProps(withDefaults<{
  size: 'small' | 'medium' | 'large';
  disabled: boolean;
}>(), {
  size: 'medium',
  disabled: false
});
```

### 4.3 事件设计
- 事件名使用 kebab-case
- 事件应使用 TypeScript 类型定义
- 事件应清晰表达其意图

**示例：**
```typescript
const emit = defineEmits<{
  (e: 'click'): void;
  (e: 'change', value: string): void;
}>();
```

### 4.4 状态管理
- 组件内部状态使用 ref 或 reactive
- 复杂状态使用 Pinia 或 Vuex
- 状态应清晰、可预测

### 4.5 组合式函数
- 组合式函数应使用 camelCase 命名
- 组合式函数应返回相关的状态和方法
- 组合式函数应具有良好的文档

**示例：**
```typescript
function useCounter(initialValue = 0) {
  const count = ref(initialValue);
  const increment = () => count.value++;
  const decrement = () => count.value--;
  
  return {
    count,
    increment,
    decrement
  };
}
```

## 5. ESLint 和 Prettier 配置

### 5.1 ESLint 配置
- 已配置 ESLint 规则，包括命名规范、代码风格和 Vue 特定规则
- 运行 `npm run lint` 检查代码

### 5.2 Prettier 配置
- 已配置 Prettier 规则，确保代码格式一致
- 运行 `npm run format` 格式化代码

## 6. 最佳实践

1. **类型安全**：使用 TypeScript 进行类型检查，确保代码类型安全
2. **组件复用**：设计可复用的组件，减少代码冗余
3. **性能优化**：使用 computed、watchEffect 等优化性能
4. **代码可读性**：编写清晰、简洁的代码，添加适当的注释
5. **测试**：为组件和函数编写测试，确保代码质量
6. **文档**：为组件和函数添加文档，便于团队成员理解

## 7. 工具使用

- **IDE**：推荐使用 VS Code，安装 ESLint 和 Prettier 插件
- **Git**：使用 Git 进行版本控制，遵循 Git 提交规范
- **包管理**：使用 npm 或 yarn 进行包管理

## 8. 提交规范

- 提交信息应清晰、简洁
- 提交信息应遵循以下格式：
  ```
  <type>(<scope>): <subject>
  ```
  
  其中，type 可以是：
  - feat: 新功能
  - fix: 修复 bug
  - docs: 文档更新
  - style: 代码风格更新
  - refactor: 代码重构
  - test: 测试更新
  - chore: 构建或依赖更新

  示例：
  ```
  feat(button): 添加按钮组件
  fix(input): 修复输入框验证问题
  docs: 更新 README.md
  ```

---

本规范旨在确保 PPTTalK 项目的前端代码质量和一致性，团队成员应严格遵循本规范。
