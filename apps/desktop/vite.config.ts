import {resolve} from "node:path";
import {fileURLToPath} from "node:url";

import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "../..");

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    fs: {allow: [repoRoot]},
  },
  envPrefix: ["VITE_", "TAURI_"],
  test: {environment: "jsdom"},
});
