// @ts-check
import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";
import preact from "@astrojs/preact";

export default defineConfig({
  output: "static",
  site: "https://emalro.com.ar",
  integrations: [
    tailwind(),
    // The contact form (PR #4) and the admin SPA (PR #5) ship as
    // Preact islands. @astrojs/preact is the official integration;
    // it compiles `.tsx` files with Preact's JSX runtime
    // (`/** @jsxImportSource preact */` at the top of each component
    // makes the runtime explicit). The public site stays static
    // (Astro renders the page shell at build time; only the form
    // hydrates client-side via `client:load`).
    preact(),
  ],
  // The admin SPA (PR #5b) uses shadcn/ui components which are
  // written for React (`import * as React from "react"`). We
  // alias `react` and `react-dom` to `preact/compat` so the shadcn
  // source resolves to Preact at build time, keeping the admin
  // bundle small (Preact 3 KB gzipped vs React 45 KB). The same
  // alias is mirrored in tsconfig.json's `paths` for the editor.
  vite: {
    resolve: {
      alias: {
        react: "preact/compat",
        "react-dom": "preact/compat",
        "react/jsx-runtime": "preact/jsx-runtime",
      },
    },
  },
});
