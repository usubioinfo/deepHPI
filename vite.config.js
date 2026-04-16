import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: process.env.DEEPHPI_BASE_PATH || "/",
  plugins: [tailwindcss(), react()],
  server: {
    port: 5173,
  },
});
