// PBI-019: Hermes agent registry — machine-readable mirror of docs/03-agents.md roster.
// Single source of truth for code; docs/03-agents.md stays human truth. Tests assert equality.

export const AGENTS = {
  ceo:        { name: 'CEO',              model: 'anthropic/claude-sonnet-4-6', trigger: 'always_on',            budgetCapUsdMonth: 30, output: 'task assignments, brand decisions' },
  trendScout: { name: 'Trend Scout',      model: 'google/gemini-2.0-flash-001', trigger: 'cron Mon 08:00',       budgetCapUsdMonth: 6,  output: '/workspace/design_briefs.json' },
  copy:       { name: 'Copy Agent',       model: 'anthropic/claude-sonnet-4-6', trigger: 'on_task',              budgetCapUsdMonth: 15, output: '/workspace/listing_copy.json' },
  design:     { name: 'Design Agent',     model: 'black-forest-labs/flux.2-pro', trigger: 'on_task',             budgetCapUsdMonth: 30, output: 'PNG + FW product live',
                fallbackModel: 'google/gemini-3.1-flash-image' },
  listing:    { name: 'Listing Agent',    model: 'google/gemini-2.0-flash-001', trigger: 'on_task',              budgetCapUsdMonth: 5,  output: 'FW listing published' },
  social:     { name: 'Social Agent',     model: 'anthropic/claude-haiku-4-5',  trigger: 'cron Tue/Wed/Thu 11am ET', budgetCapUsdMonth: 4, output: 'scheduled posts' },
  video:      { name: 'Video Agent',      model: 'google/veo-3.1-lite',         trigger: 'cron Mon+Thu 10:00',   budgetCapUsdMonth: 20, output: '8s product clips',
                orchestratorModel: 'anthropic/claude-haiku-4-5' },
  analytics:  { name: 'Analytics Agent',  model: 'anthropic/claude-haiku-4-5',  trigger: 'cron Fri 18:00',       budgetCapUsdMonth: 3,  output: '/workspace/weekly_report.md + kill_list.md' },
  email:      { name: 'Email Agent',      model: 'anthropic/claude-sonnet-4-6', trigger: 'cron Sat 09:00',       budgetCapUsdMonth: 5,  output: 'newsletter sent (Loops.so)' },
  community:  { name: 'Community Agent',  model: 'anthropic/claude-haiku-4-5',  trigger: 'cron every 12h',       budgetCapUsdMonth: 4,  output: 'replies, engagement' },
  finance:    { name: 'Finance Agent',    model: 'google/gemini-2.0-flash-001', trigger: 'cron 1st of month',    budgetCapUsdMonth: 2,  output: '/workspace/finance_report.md' }
};

export const TOTAL_BUDGET_CAP_USD_MONTH = 130; // AGENTS.md §3 discipline

export function getAgent(key) {
  const a = AGENTS[key];
  if (!a) throw new Error(`unknown agent "${key}" — known: ${Object.keys(AGENTS).join(', ')}`);
  return a;
}

export function listAgents() {
  return Object.entries(AGENTS).map(([key, a]) => ({ key, ...a }));
}
