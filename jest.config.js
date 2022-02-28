const resolveConfig = require('./webpack.config.resolve');

const moduleNameMapper = {};
Object.keys(resolveConfig.resolve.alias).forEach((key) => {
  // CAUTION: changing the .split method could break testing on CircleCI
  moduleNameMapper[`\\${key}/(.*)`] = `<rootDir>/src${resolveConfig.resolve.alias[key].split('src')[1]}/$1`;
});

// jest.config.js
module.exports = {
  verbose: true,
  roots: ['<rootDir>/src'],
  testPathIgnorePatterns: [
    'config',
  ],
  setupFilesAfterEnv: ['<rootDir>/src/__tests__/jest-setup.js'],
  modulePaths: ['src'],
  moduleFileExtensions: ['js', 'jsx'],
  moduleDirectories: ['node_modules', 'bower_components', 'shared'],
  testMatch: [
    '<rootDir>/src/__tests__/**/*.test.{js,jsx,ts,tsx}',
  ],
  // Indicates whether the coverage information should be collected while executing the test
  // collectCoverage: true,
  // The directory where Jest should output its coverage files
  // coverageDirectory: 'jest-coverage',
  // The test environment that will be used for testing
  // testEnvironment: 'node',
  moduleNameMapper: {
    '\\$images/inline-svg/*': '<rootDir>/src/__mocks__/svgrMock.js',
    '\\.(jpg|jpeg|png|gif|eot|otf|webp|svg|ttf|woff|woff2|mp4|webm|wav|mp3|m4a|aac|oga)$': '<rootDir>/src/__mocks__/fileMock.js',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    ...moduleNameMapper,
  },
};
