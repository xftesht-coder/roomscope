import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  build: {
    rollupOptions: {
      input: [
        "index.html",
        "roadmap.html",
        "presentation.html",
        "workspace.html",
      ],
    },
  },
});
