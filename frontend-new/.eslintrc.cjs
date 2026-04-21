module.exports = {
  root: true,
  env: {
    browser: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    '@vue/typescript/recommended',
    'plugin:vue/vue3-recommended',
    'eslint-config-prettier'
  ],
  parserOptions: {
    ecmaVersion: 2020,
    parser: '@typescript-eslint/parser'
  },
  plugins: [
    '@typescript-eslint',
    'vue'
  ],
  rules: {
    // 命名规范
    '@typescript-eslint/naming-convention': [
      'error',
      {
        selector: 'interface',
        format: ['PascalCase']
      },
      {
        selector: 'typeAlias',
        format: ['PascalCase']
      },
      {
        selector: 'class',
        format: ['PascalCase']
      },
      {
        selector: 'enum',
        format: ['PascalCase']
      },
      {
        selector: 'variable',
        format: ['camelCase', 'UPPER_CASE'],
        leadingUnderscore: 'allow'
      },
      {
        selector: 'function',
        format: ['camelCase']
      }
    ],
    // 代码风格
    'indent': ['error', 2, { 'SwitchCase': 1 }],
    'linebreak-style': ['error', 'unix'],
    'quotes': ['error', 'single'],
    'semi': ['error', 'always'],
    'no-trailing-spaces': 'error',
    'object-curly-spacing': ['error', 'always'],
    'array-bracket-spacing': ['error', 'never'],
    'space-infix-ops': 'error',
    'space-before-function-paren': ['error', 'always'],
    // Vue 特定规则
    'vue/multi-word-component-names': 'off',
    'vue/script-setup-uses-vars': 'error',
    'vue/attribute-hyphenation': 'error',
    'vue/html-self-closing': [
      'error',
      {
        html: {
          void: 'always',
          normal: 'always',
          component: 'always'
        }
      }
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
          'methods'
        ]
      }
    ]
  }
};
