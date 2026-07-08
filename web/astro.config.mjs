// @ts-check
import { defineConfig } from 'astro/config';

// Static site for the Mut 1683 single-sheet map.
export default defineConfig({
  site: 'https://example.com',
  // Per desplegar a un subdirectori, descomenta i ajusta:
  // base: '/mapa-mut',
  build: {
    format: 'directory',
  },
  // Amaga la barra d'eines de desenvolupament d'Astro (només sortia en mode dev).
  devToolbar: {
    enabled: false,
  },
  server: {
    port: 4330,
  },
});
