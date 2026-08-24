/**
 * Combining the rule score with the ML score.
 *
 * This is the hinge of the hybrid design, and the obvious choice turns out to
 * be the wrong one for this system.
 *
 * The specification suggests a weighted mean. Phases 4 and 5 measured why that
 * fails here: the classifiers assign zero importance to four of the five flow
 * features, because those are zero-filled throughout the offline corpus, so a
 * brute-force or credential-stuffing vector scores about 0.027 at the inference
 * service. Under a weighted mean, a rule engine that is 0.90 confident of a
 * brute-force attack would produce
 *
 *     0.5 * 0.90 + 0.5 * 0.027 = 0.46
 *
 * which falls below the 0.7 threshold. The hybrid would therefore detect *less*
 * than rules alone on two of the three target attacks — the ML term does not
 * merely fail to help, it actively cancels a correct detection.
 *
 * The default strategy is instead a noisy-OR, the standard combination for two
 * independent sources of evidence:
 *
 *     combined = 1 - (1 - rule) * (1 - ml)
 *
 * Properties that matter here:
 *   - never below either input, so neither stage can cancel the other
 *   - corroboration is rewarded: 0.5 and 0.5 combine to 0.75, because two
 *     independent weak signals are stronger than either alone
 *   - stays within [0, 1] and is monotonic in both inputs
 *
 * All four strategies are implemented and selectable, because the comparison is
 * itself a result worth reporting in Phase 9 rather than a decision to justify
 * by argument.
 */

/**
 * Put the ML score on the same scale as the rule score before combining.
 *
 * The two are not natively comparable. The rule score is an accumulation of
 * evidence weights; the ML score is a weighted blend of three model outputs
 * whose decision boundary was fitted on a validation split and sits at 0.77,
 * not at 0.5. Combining them raw reads an ML score of 0.79 as "79% confident"
 * when what it actually means is "just over the line".
 *
 * That mismatch is not academic. Measured on this API, a benign search scores
 * 0.79 and a benign login 0.837 at the inference service — both marginal
 * verdicts. Fed raw into a noisy-OR, which never reduces a score, they alone
 * cleared the 0.7 block threshold and rejected legitimate traffic.
 *
 * This maps the ML score piecewise so its own boundary lands at 0.5: below the
 * boundary compresses into [0, 0.5], above it into [0.5, 1]. A marginal verdict
 * then contributes marginal evidence, and only a confident one can carry a
 * request over the threshold on its own.
 */
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

/**
 * @param {number} ruleScore  rule engine score in [0, 1]
 * @param {number|null} mlScore  ML score in [0, 1], or null when unavailable
 * @param {object} opts  { strategy, wRule, wMl }
 * @returns {{ score: number, strategy: string, mlUsed: boolean }}
 */
function combine(ruleScore, mlScore, opts = {}) {
  const rule = clamp01(ruleScore);
  const name = opts.strategy || DEFAULT_STRATEGY;
  const fn = STRATEGIES[name] || STRATEGIES[DEFAULT_STRATEGY];

  // No ML score means the service was unavailable, or this request never
  // reached it. Fall back to the rule verdict unchanged; do not treat a missing
  // score as evidence of innocence, and do not treat it as evidence of guilt.
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
