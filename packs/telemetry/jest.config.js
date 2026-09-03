export default {
  testEnvironment: "node",
  collectCoverageFrom: [
    "behavior_pack/scripts/**/*.js",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["lcov", "text-summary"],
  coverageThreshold: {
    global: {
      branches: 86,
      functions: 98,
      lines: 99,
      statements: 94,
    },
  },
  reporters: [
    "default",
    ["jest-junit", { outputDirectory: ".", outputName: "junit.xml" }],
  ],
  moduleNameMapper: {
    "^@minecraft/server$": "<rootDir>/tests/minecraft-server.mock.js",
  },
};
