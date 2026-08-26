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
