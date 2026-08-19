/**
 * Rule-based detection: stage one of the hybrid cascade.
 *
 * Deterministic, interpretable and cheap. Every rule reads only the shared
 * feature vector produced by featureExtractor.js, deliberately: the rule
 * filter and the ML classifier judge the same representation of a request,
 * which is what makes their scores combinable in stage two.
 *
 * Returns { blocked, alerts, ruleScore }:
 *   blocked   - true if any high-severity rule fired; the request is rejected
 *               without consulting the classifier
 *   alerts    - what fired, for logging and for explaining a decision
 *   ruleScore - clamped to [0, 1], combined with the ML score in Phase 6
 *
 * Thresholds are exported so the evaluation in Phase 9 can sweep them when
 * measuring the rule-only baseline against the hybrid configuration.
 */

const THRESHOLDS = {
  SQL_KEYWORDS_STRONG: 5,
  SQL_KEYWORDS_MODERATE: 3,
  SQL_KEYWORDS_WITH_COMMENT: 2,
  SPECIAL_CHAR_RATIO: 0.12,
  SINGLE_QUOTES: 4,
  RATE_HIGH: 60,
  RATE_MODERATE: 30,
  LOGIN_FAILURE_RATIO: 0.8,
  LOGIN_FAILURE_MIN_REQUESTS: 5,
  DISTINCT_USERNAMES_HIGH: 5,
  DISTINCT_USERNAMES_MODERATE: 3,
};

const HIGH = 'high';
const MEDIUM = 'medium';

/**
 * Each rule is a predicate over the feature vector plus a severity and a
 * weight. Keeping them as data rather than as a chain of if-statements means
 * the active rule set can be printed, tuned and reported in the evaluation.
 */
const RULES = [
  {
    id: 'SQLI_UNION_SELECT',
    severity: HIGH,
    weight: 1.0,
    message: 'UNION SELECT construction present in request',
    test: (f) => f.has_union_select === 1,
  },
  {
    id: 'SQLI_TAUTOLOGY_CONFIRMED',
    severity: HIGH,
    weight: 0.9,
    message: 'Boolean tautology alongside quoting or multiple SQL keywords',
    test: (f) =>
      f.has_or_equals === 1 &&
      (f.single_quote_count >= 1 || f.sql_keyword_count >= THRESHOLDS.SQL_KEYWORDS_MODERATE),
  },
  {
    id: 'SQLI_COMMENT_WITH_KEYWORDS',
    severity: HIGH,
    weight: 0.8,
    message: 'SQL comment marker combined with SQL keywords',
    test: (f) =>
      f.has_comment === 1 && f.sql_keyword_count >= THRESHOLDS.SQL_KEYWORDS_WITH_COMMENT,
  },
  {
    id: 'SQLI_KEYWORD_DENSITY',
    severity: HIGH,
    weight: 0.8,
    message: 'High SQL keyword count with elevated special-character ratio',
    test: (f) =>
      f.sql_keyword_count >= THRESHOLDS.SQL_KEYWORDS_STRONG &&
      f.special_char_ratio >= THRESHOLDS.SPECIAL_CHAR_RATIO,
  },
  {
    id: 'SQLI_TAUTOLOGY_WEAK',
    severity: MEDIUM,
    weight: 0.4,
    message: 'Boolean tautology pattern without corroborating signal',
    test: (f) => f.has_or_equals === 1,
  },
  {
    id: 'SQLI_KEYWORDS_MODERATE',
    severity: MEDIUM,
    weight: 0.35,
    message: 'Several SQL keywords present',
    test: (f) => f.sql_keyword_count >= THRESHOLDS.SQL_KEYWORDS_MODERATE,
  },
  {
    id: 'SQLI_QUOTE_DENSITY',
    severity: MEDIUM,
    weight: 0.3,
    message: 'Unusual number of quote characters',
    test: (f) => f.single_quote_count >= THRESHOLDS.SINGLE_QUOTES,
  },
  {
    id: 'SQLI_STACKED_QUERY',
    severity: MEDIUM,
    weight: 0.7,
    message: 'Statement separator combined with SQL keywords',
    // Weighted to reach the default threshold unaided: a semicolon plus two
    // or more SQL keywords in a query parameter is a stacked-query attempt
    // and has little legitimate use. Left at medium severity rather than
    // high so the ML stage is still consulted in hybrid mode.
    test: (f) => f.semicolon_count >= 1 && f.sql_keyword_count >= 2,
  },
  {
    id: 'SQLI_OBFUSCATED_TAUTOLOGY',
    severity: MEDIUM,
    weight: 0.5,
    message: 'Tautology pattern interleaved with comment syntax (obfuscation)',
    // Catches the inline-comment evasion described by Qu et al. (2024), e.g.
    // /**/or/**/1/**/=/**/1, where the comment markers split the tautology so
    // that no single strong indicator fires. Composes with SQLI_TAUTOLOGY_WEAK
    // (0.4) to 0.9, which clears the threshold; neither alone would.
    test: (f) => f.has_or_equals === 1 && f.has_comment === 1,
  },
  {
    id: 'SQLI_QUOTE_WITH_COMMENT',
    severity: MEDIUM,
    weight: 0.5,
    message: 'Quote character co-occurring with SQL comment syntax',
    // Deliberately medium. The has_comment flag also covers '#', which is
    // common in benign text ("item #5"), so promoting this to high severity
    // would cost false positives. Phase 9 sweeps these weights.
    test: (f) => f.single_quote_count >= 1 && f.has_comment === 1,
  },
  {
    id: 'RATE_EXCESSIVE',
    severity: HIGH,
    weight: 0.9,
    message: 'Request rate from source far above normal',
    test: (f) => f.requests_per_min_ip > THRESHOLDS.RATE_HIGH,
  },
  {
    id: 'RATE_ELEVATED',
    severity: MEDIUM,
    weight: 0.4,
    message: 'Request rate from source elevated',
    test: (f) => f.requests_per_min_ip > THRESHOLDS.RATE_MODERATE,
  },
  {
    id: 'AUTH_FAILURE_RATIO',
    severity: HIGH,
    weight: 0.85,
    message: 'Sustained authentication failures from source',
    test: (f) =>
      f.login_failure_ratio >= THRESHOLDS.LOGIN_FAILURE_RATIO &&
      f.requests_per_min_ip >= THRESHOLDS.LOGIN_FAILURE_MIN_REQUESTS,
  },
  {
    id: 'CREDENTIAL_STUFFING',
    severity: HIGH,
    weight: 0.85,
    message: 'Many distinct usernames attempted from one source',
    test: (f) => f.distinct_usernames_tried >= THRESHOLDS.DISTINCT_USERNAMES_HIGH,
  },
  {
    id: 'USERNAME_SPRAY',
    severity: MEDIUM,
    weight: 0.4,
    message: 'Multiple distinct usernames attempted from one source',
    test: (f) => f.distinct_usernames_tried >= THRESHOLDS.DISTINCT_USERNAMES_MODERATE,
  },
];

function evaluate(features) {
  const alerts = [];
  let score = 0;
  let blocked = false;

  for (const rule of RULES) {
    let fired = false;
    try {
      fired = !!rule.test(features);
    } catch (err) {
      // A malformed feature vector must not take the request path down.
      fired = false;
    }
    if (!fired) continue;

    alerts.push({
      id: rule.id,
      severity: rule.severity,
      weight: rule.weight,
      message: rule.message,
    });
    score += rule.weight;
    if (rule.severity === HIGH) blocked = true;
  }

  return { blocked, alerts, ruleScore: Math.min(1, score) };
}

module.exports = { evaluate, RULES, THRESHOLDS, HIGH, MEDIUM };
