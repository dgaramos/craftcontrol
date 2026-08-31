export default {
  testEnvironment: "node",
  collectCoverageFrom: [
    "behavior_pack/scripts/**/*.js",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["lcov", "text-summary"],
};
