const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const config = require('./config');

const authRoutes = require('./routes/auth');
const searchRoutes = require('./routes/search');
const ordersRoutes = require('./routes/orders');
const detectionMiddleware = require('./middleware/detection');
const featureExtractor = require('./middleware/featureExtractor');
const { pool } = require('./db/pool');

const app = express();

// See config/index.js for why this is opt-in and why the default matters.
// Logged loudly because a detection system that trusts a spoofable source
// header should never do so silently.
if (config.trustProxy) {
  app.set('trust proxy', true);
  console.warn('[config] TRUST_PROXY=1: X-Forwarded-For is trusted as the ' +
               'request source. Intended for the Phase 8 simulation harness ' +
               'only -- behavioural detection is bypassable in this mode.');
}

app.use(helmet());
app.use(morgan('dev'));
app.use(express.json());

app.get('/health', (req, res) => {
  // `window` reports how much per-source state the behavioural features are
  // currently holding: counts only, never addresses. It exists so a test can
  // tell "this source has a clean window" from "this source is still inside a
  // window left by the previous run" -- a distinction that otherwise shows up
  // as an unexplained failure several checks later.
  res.status(200).json({ status: 'ok', window: featureExtractor.storeStats() });
});

// Every /api/* request is inspected before it reaches a route handler.
app.use('/api', detectionMiddleware);

app.use('/api/auth', authRoutes);
app.use('/api/search', searchRoutes);
app.use('/api/orders', ordersRoutes);

if (require.main === module) {
  const server = app.listen(config.port, () => {
    console.log(`API listening on port ${config.port}`);
  });

  /**
   * Shut down on a signal instead of being killed mid-request.
   *
   * `docker compose stop` sends SIGTERM and waits ten seconds before SIGKILL.
   * With no handler, Node's default action for SIGTERM is immediate
   * termination: every request being served at that moment is dropped, and the
   * Postgres connections are left for the server to time out. That matters here
   * because the evaluation depends on request_log being a complete record of
   * what the API saw — a truncated write at shutdown is a missing row in the
   * results.
   *
   * server.close() stops accepting new connections and waits for the ones in
   * flight, then the pool is drained and the sliding-window timer cleared so
   * the event loop can empty on its own.
   */
  let shuttingDown = false;

  async function shutdown(signal) {
    if (shuttingDown) return;   // a second Ctrl-C should not re-enter this
    shuttingDown = true;
    console.log(`[shutdown] ${signal} received, draining`);

    // Backstop: if a client holds a connection open, do not hang forever.
    const forceExit = setTimeout(() => {
      console.error('[shutdown] drain timed out after 8s, exiting anyway');
      process.exit(1);
    }, 8000);
    forceExit.unref();

    server.close(async () => {
      try {
        featureExtractor.stopSweep();
        await pool.end();
        console.log('[shutdown] clean');
        process.exit(0);
      } catch (err) {
        console.error('[shutdown] error while closing:', err.message);
        process.exit(1);
      }
    });
  }

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

module.exports = app;
