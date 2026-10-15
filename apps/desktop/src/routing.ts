/** Hash routes passed through to engine `fetch_view(route)`. */

export function routeFromHash(hash: string): string {
  if (!hash || hash === "#") {
    return "#/research";
  }
  return hash.startsWith("#") ? hash : `#${hash}`;
}

export function readBrowserRoute(): string {
  return routeFromHash(window.location.hash);
}
