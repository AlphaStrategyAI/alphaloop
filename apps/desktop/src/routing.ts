/** Hash routes passed through to engine `fetch_view(route)`. */

function decodeRouteSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export function routeFromHash(hash: string): string {
  if (!hash || hash === "#") {
    return "#/research";
  }
  const raw = hash.startsWith("#") ? hash : `#${hash}`;
  if (raw.startsWith("#/methods/")) {
    const id = decodeRouteSegment(raw.slice("#/methods/".length).split("?")[0] ?? "");
    return `#/methods/${id}`;
  }
  if (raw.startsWith("#/research/")) {
    const id = decodeRouteSegment(raw.slice("#/research/".length).split("?")[0] ?? "");
    return `#/research/${id}`;
  }
  return raw;
}

export function readBrowserRoute(): string {
  return routeFromHash(window.location.hash);
}
