import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("react-router")) return "vendor-router";
            if (id.includes("@tanstack/react-query") || id.includes("axios")) return "vendor-data";
            if (id.includes("react-markdown") || id.includes("remark-")) return "vendor-markdown";
            if (id.includes("react") || id.includes("scheduler")) return "vendor-react";
          }

          if (id.includes("/features/documents/")) return "feature-documents";
          if (id.includes("/features/workspace/")) return "feature-workspace";
          if (id.includes("/features/analysis/")) return "feature-analysis";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: true,
    fileParallelism: false,
    maxWorkers: 1,
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
