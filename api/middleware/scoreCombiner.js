function alignToBoundary(score, boundary) {
  const b = (boundary > 0 && boundary < 1) ? boundary : 0.5;
  return score <= b
    ? 0.5 * (score / b)
    : 0.5 + 0.5 * ((score - b) / (1 - b));
}

const STRATEGIES = {
  /** 1 - (1-r)(1-m). Default. Neither stage can cancel the other. */
  noisy_or: (rule, ml) => 1 - (1 - rule) * (1 - ml),

  /** The specification's weighted mean. Retained for comparison. */
  weighted: (rule, ml, opts) => opts.wRule * rule + opts.wMl * ml,

  /** Strongest single signal. No dilution, but no corroboration benefit. */
  max: (rule, ml) => Math.max(rule, ml),

  /** Ignores the ML term entirely; the rule-only baseline. */
  rules_only: (rule) => rule,
};

const DEFAULT_STRATEGY = 'noisy_or';

function clamp01(x) {
  if (!Number.isFinite(x)) return 0;
  return Math.min(1, Math.max(0, x));
}

// ruleScore and mlScore are both in [0, 1]; mlScore is null when the service
// was unavailable or never consulted. Returns { score, strategy, mlUsed }.
function combine(ruleScore, mlScore, opts = {}) {
  const rule = clamp01(ruleScore);
  const name = opts.strategy || DEFAULT_STRATEGY;
  const fn = STRATEGIES[name] || STRATEGIES[DEFAULT_STRATEGY];

  // A missing ML score is not evidence either way, so fall back to the rule
  // verdict unchanged rather than scoring the absence.
  if (mlScore === null || mlScore === undefined) {
    return { score: rule, strategy: `${name} (rule-only fallback)`, mlUsed: false };
  }

  const raw = clamp01(mlScore);
  const ml = opts.mlBoundary ? clamp01(alignToBoundary(raw, opts.mlBoundary)) : raw;
  const score = clamp01(fn(rule, ml, {
    wRule: opts.wRule == null ? 0.5 : opts.wRule,
    wMl: opts.wMl == null ? 0.5 : opts.wMl,
  }));

  return { score, strategy: name, mlUsed: true, mlRaw: raw, mlAligned: ml };
}

module.exports = { combine, STRATEGIES, DEFAULT_STRATEGY };
