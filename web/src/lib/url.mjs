// Construeix URLs respectant el `base` configurat a astro.config.mjs.
const BASE = import.meta.env.BASE_URL || '/';

export function url(path = '') {
  const clean = String(path).replace(/^\//, '');
  return (BASE.endsWith('/') ? BASE : BASE + '/') + clean;
}
