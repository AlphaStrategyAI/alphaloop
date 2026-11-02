import type {ExportKind} from "../contracts";
import {enCatalog, zhCatalog} from "./catalog";

export type MatchedRuntimeCommand =
  | {type: "pause"}
  | {type: "resume"}
  | {type: "reverify"}
  | {type: "export_artifact"; kind: ExportKind}
  | {type: "continue_iterate"};

function normalize(text: string): string {
  return text.trim().toLowerCase();
}

function phrases(...values: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const value of values) {
    const text = value.trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    unique.push(text);
  }
  return unique;
}

const groups: ReadonlyArray<{phrases: readonly string[]; command: MatchedRuntimeCommand}> = [
  {
    phrases: phrases("暂停", "pause", zhCatalog.ui.running.pause, enCatalog.ui.running.pause),
    command: {type: "pause"},
  },
  {
    phrases: phrases("恢复", "resume", zhCatalog.ui.running.resume, enCatalog.ui.running.resume),
    command: {type: "resume"},
  },
  {
    phrases: phrases("重验", "reverify", zhCatalog.ui.completed.reverify, enCatalog.ui.completed.reverify),
    command: {type: "reverify"},
  },
  {
    phrases: phrases(
      "导出策略包",
      "export strategy pack",
      zhCatalog.ui.export.strategyPack,
      enCatalog.ui.export.strategyPack,
    ),
    command: {type: "export_artifact", kind: "strategy_pack"},
  },
  {
    phrases: phrases(
      "导出研究记录",
      "export research record",
      zhCatalog.ui.export.researchRecord,
      enCatalog.ui.export.researchRecord,
    ),
    command: {type: "export_artifact", kind: "research_record"},
  },
  {
    phrases: phrases(
      "继续迭代",
      "continue iterating",
      zhCatalog.ui.completed.iterateTitle,
      enCatalog.ui.completed.iterateTitle,
    ),
    command: {type: "continue_iterate"},
  },
];

const byNormalized = new Map<string, MatchedRuntimeCommand>();
for (const group of groups) {
  for (const phrase of group.phrases) {
    byNormalized.set(normalize(phrase), group.command);
  }
}

/** Short aliases plus both locales' button labels. Exact match after trim and case fold. */
export function matchRuntimeUtterance(text: string): MatchedRuntimeCommand | null {
  return byNormalized.get(normalize(text)) ?? null;
}

export function runtimeUtteranceExamples(): ReadonlyArray<{text: string; command: MatchedRuntimeCommand}> {
  return groups.flatMap((group) => group.phrases.map((text) => ({text, command: group.command})));
}
