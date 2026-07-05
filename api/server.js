const express = require('express');
const helmet = require('helmet');
const morgan = require('morgan');
const config = require('./config');

const authRoutes = require('./routes/auth');
const searchRoutes = require('./routes/search');
const ordersRoutes = require('./routes/orders');

const app = express();

app.use(helmet());
app.use(morgan('dev'));
app.use(express.json());

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// TODO (Phase 3): app.use('/api', detectionMiddleware) goes here, before
// the routes below, so every /api/* request is inspected first.
app.use('/api/auth', authRoutes);
app.use('/api/search', searchRoutes);
app.use('/api/orders', ordersRoutes);

if (require.main === module) {
  app.listen(config.port, () => {
    console.log(`API listening on port ${config.port}`);
  });
}

module.exports = app;
