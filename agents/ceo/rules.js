// PBI-006: CEO decision rules — pure functions (specs/platform-workspace contracts 2,3)
// No I/O, no LLM calls. Tests own 100% branch coverage.

export function decideApproveBrief(score) {
  return typeof score === 'number' && score >= 60;
}

export function decideKill(daysSincePublish, sales) {
  return daysSincePublish > 30 && sales === 0;
}

export function decideScale(salesLast14Days) {
  return salesLast14Days >= 5;
}

export function decideFlashSale(wowRevenueChange) {
  // wowRevenueChange as ratio, e.g. -0.30 = -30%
  return typeof wowRevenueChange === 'number' && wowRevenueChange <= -0.30;
}
