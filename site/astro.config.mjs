// @ts-check
import { defineConfig } from 'astro/config';

// SITE_BASE lets the same build serve from a subpath, e.g. GitHub Pages at /congress_insights.
export default defineConfig({
  base: process.env.SITE_BASE ?? '/',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
});
