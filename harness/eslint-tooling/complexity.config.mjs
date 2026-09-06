import tsParser from "@typescript-eslint/parser";

// Standalone config used only for scoring: parses every function in a file
// and reports its cyclomatic complexity, regardless of how simple it is.
// Threshold 0 means every function triggers a message, turning `complexity`
// into a metric report rather than a pass/fail lint rule.
export default [
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {
      complexity: ["warn", 0],
    },
  },
];
