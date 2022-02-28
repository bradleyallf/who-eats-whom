module.exports = {
  extends: [
    'airbnb',
    'plugin:cypress/recommended',
  ],
  parser: 'babel-eslint',
  env: {
    browser: true,
    es6: true,
    mocha: true,
    node: true,
    atomtest: true
  },
  plugins: [
    'react',
    'jsx-a11y',
    'react-hooks',
    'import'
  ],
  parserOptions: {
    ecmaVersion: 6,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true
    }
  },
  rules: {
    'arrow-body-style': 'off',
    'semi': 'error',
    'max-len': ['warn', 120],
    'class-methods-use-this': 'off',
    'react/button-has-type': 'off',
    'react/destructuring-assignment': 'off',
    'react/prefer-stateless-function': 'off',
    'react/jsx-filename-extension': 'off',
    'jsx-a11y/img-has-alt': 'off',
    'jsx-a11y/anchor-is-valid': 'off',
    'global-require': 'off',
    'no-class-assign': 'off',
    'one-var': 'off',
    'one-var-declaration-per-line': 'off',
    'import/prefer-default-export': 'off',
    'react/sort-comp': 'off',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn'
  },
  settings: {
    'import/resolver': {
      node: {}, // https://github.com/benmosher/eslint-plugin-import/issues/1396#issuecomment-509384041
      webpack: {
        config: './webpack.config.resolve.js'
      },
    }
  }
}
