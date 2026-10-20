import type {DesktopView} from "../contracts";

export function routeFor(view: DesktopView): string {
  if (view.kind === "research_list") return "#/research";
  if (view.kind === "methods") return `#/methods${view.selected ? `/${view.selected}` : ""}`;
  if (view.kind === "glossary") return "#/glossary";
  return `#/research/${view.researchId}`;
}

