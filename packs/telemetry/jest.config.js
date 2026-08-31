export default {
  testEnvironment: "node",
  collectCoverageFrom: [
    "behavior_pack/scripts/**/*.js",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["lcov", "text-summary"],
  reporters: [
    "default",
    ["jest-junit", { outputDirectory: ".", outputName: "junit.xml" }],
  ],
  moduleNameMapper: {
    "^@minecraft/server$": "<rootDir>/tests/minecraft-server.mock.js",
  },
};
