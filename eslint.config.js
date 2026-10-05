import js from "@eslint/js";
import globals from "globals";
export default [
  {
    ignores: [
      "dist/**",
      ".venv/**",
      "test-results/**",
      "playwright-report/**",
      "public/**",
    ],
  },
  js.configs.recommended,
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
];
