import vue from 'eslint-plugin-vue';
import typescriptParser from '@typescript-eslint/parser';
import typescriptPlugin from '@typescript-eslint/eslint-plugin';

// 导入 vue-eslint-parser
import vueEslintParser from 'vue-eslint-parser';

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '*.min.js'],
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      globals: {
        browser: true,
        window: true,
        document: true,
        console: true,
        fetch: true,
        FormData: true,
        File: true,
        AbortController: true,
        TextDecoder: true,
        setInterval: true,
        clearInterval: true,
        setTimeout: true,
        clearTimeout: true,
        location: true,
        history: true,
        process: true,
      },
      parser: vueEslintParser,
      parserOptions: {
        ecmaVersion: 2020,
        parser: typescriptParser,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptPlugin,
      vue: vue,
    },
    rules: {
      // 基本规则
      'no-console': 'warn',
      'no-unused-vars': 'error',
      'no-undef': 'error',

      // 命名规范
      '@typescript-eslint/naming-convention': [
        'error',
        {
          selector: 'interface',
          format: ['PascalCase'],
        },
        {
          selector: 'typeAlias',
          format: ['PascalCase'],
        },
        {
          selector: 'class',
          format: ['PascalCase'],
        },
        {
          selector: 'enum',
          format: ['PascalCase'],
        },
        {
          selector: 'variable',
          format: ['camelCase', 'UPPER_CASE'],
          leadingUnderscore: 'allow',
        },
        {
          selector: 'function',
          format: ['camelCase'],
        },
      ],
      // 代码风格
      indent: ['error', 2, { SwitchCase: 1 }],
      'linebreak-style': ['error', 'unix'],
      quotes: ['error', 'single'],
      semi: ['error', 'always'],
      'no-trailing-spaces': 'error',
      'object-curly-spacing': ['error', 'always'],
      'array-bracket-spacing': ['error', 'never'],
      'space-infix-ops': 'error',
      'space-before-function-paren': ['error', 'always'],
      // Vue 特定规则
      'vue/multi-word-component-names': 'off',
      'vue/attribute-hyphenation': 'error',
      'vue/html-self-closing': [
        'error',
        {
          html: {
            void: 'always',
            normal: 'always',
            component: 'always',
          },
        },
      ],
      'vue/order-in-components': [
        'error',
        {
          order: [
            'defineOptions',
            'defineProps',
            'defineEmits',
            'defineExpose',
            'data',
            'computed',
            'watch',
            'lifecycle',
            'methods',
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.{js,jsx,cjs,mjs,ts,tsx,cts,mts}'],
    languageOptions: {
      globals: {
        browser: true,
        window: true,
        document: true,
        console: true,
        fetch: true,
        FormData: true,
        File: true,
        AbortController: true,
        TextDecoder: true,
        setInterval: true,
        clearInterval: true,
        setTimeout: true,
        clearTimeout: true,
        location: true,
        history: true,
        process: true,
      },
      parser: typescriptParser,
      parserOptions: {
        ecmaVersion: 2020,
      },
    },
    plugins: {
      '@typescript-eslint': typescriptPlugin,
    },
    rules: {
      // 基本规则
      'no-console': 'warn',
      'no-unused-vars': 'error',
      'no-undef': 'error',

      // 命名规范
      '@typescript-eslint/naming-convention': [
        'error',
        {
          selector: 'interface',
          format: ['PascalCase'],
        },
        {
          selector: 'typeAlias',
          format: ['PascalCase'],
        },
        {
          selector: 'class',
          format: ['PascalCase'],
        },
        {
          selector: 'enum',
          format: ['PascalCase'],
        },
        {
          selector: 'variable',
          format: ['camelCase', 'UPPER_CASE'],
          leadingUnderscore: 'allow',
        },
        {
          selector: 'function',
          format: ['camelCase'],
        },
      ],
      // 代码风格
      indent: ['error', 2, { SwitchCase: 1 }],
      'linebreak-style': ['error', 'unix'],
      quotes: ['error', 'single'],
      semi: ['error', 'always'],
      'no-trailing-spaces': 'error',
      'object-curly-spacing': ['error', 'always'],
      'array-bracket-spacing': ['error', 'never'],
      'space-infix-ops': 'error',
      'space-before-function-paren': ['error', 'always'],
    },
  },
];
