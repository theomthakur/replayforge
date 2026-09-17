import type { Metric } from "../../api/types";

export function metric(metrics: Metric[], lane: "baseline" | "candidate", name: string): Metric | undefined {
  return metrics.find((m) => m.lane === lane && m.name === name);
}

export function formatValue(m: Metric | undefined): string {
  if (!m || m.value === null || m.value === undefined) return "unknown";
  switch (m.unit) {
    case "ratio": return `${Math.round(m.value * 100)}%`;
    case "usd": return `$${m.value.toFixed(4)}`;
    case "ms": return `${(m.value / 1000).toFixed(1)} s`;
    default: return m.value.toLocaleString();
  }
}

export const KIND_LABEL: Record<string, string> = {
  measured: "measured",
  provider_reported: "provider-reported",
  derived: "derived",
  estimated: "not measurable",
};

export const OUTCOME_LABEL: Record<string, string> = {
  both_pass: "both pass",
  both_fail: "both fail",
  candidate_regressed: "regressed",
  candidate_improved: "improved",
};
