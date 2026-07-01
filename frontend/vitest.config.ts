import { defineConfig } from "vitest/config";
import preact from "@preact/preset-vite";

/**
 * Vitest configuration for the frontend unit tests.
 *
 * The contact form (PR #4) is the first feature with behavior
 * tests. The runtime uses Preact; @testing-library/preact ships
 * a Preact-aware `render` that understands the @jsxImportSource
 * directive at the top of each .tsx file.
 *
 * `happy-dom` is enough for the form tests (no canvas, no
 * WebGL). If a future test needs a more spec-compliant DOM,
 * swap to `jsdom` here without touching the test files.
 *
 * We pull in the @preact/preset-vite plugin (the same one the
 * @astrojs/preact integration uses) so vitest 4's bundler picks
 * up the Preact JSX transform. Without it, vitest 4's default
 * parser treats JSX as plain TSX and the test files fail to
 * compile.
 */
export default defineConfig({
  plugins: [preact()],
  test: {
    environment: "happy-dom",
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
    isolate: true,
  },
});
