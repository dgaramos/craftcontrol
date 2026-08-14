export default {
  testEnvironment: "node",
  moduleNameMapper: {
    // Strip ?v=... query strings from imports
    "^(.*\\.js)\\?.*$": "$1",
  },
  collectCoverageFrom: [
    "static/js/**/*.js",
    "!static/js/app.js",
    "!static/js/auth.js",
    "!static/js/composition.js",
  ],
  coverageDirectory: "coverage",
  coverageReporters: ["lcov", "text-summary"],
  reporters: ["default", ["jest-junit", { outputDirectory: ".", outputName: "junit.xml" }]],
};
