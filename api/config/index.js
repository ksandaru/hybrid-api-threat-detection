require('dotenv').config();

module.exports = {
  port: parseInt(process.env.PORT, 10) || 3000,
  mlServiceUrl: process.env.ML_SERVICE_URL || 'http://localhost:8000',
  databaseUrl: process.env.DATABASE_URL,
  detectionThreshold: parseFloat(process.env.DETECTION_THRESHOLD) || 0.7,
  detectionMode: process.env.DETECTION_MODE || 'rules',
  jwtSecret: process.env.JWT_SECRET || 'change-me-in-local-env',
  trustProxy: process.env.TRUST_PROXY === '1',
  mlPayloadPaths: (process.env.ML_PAYLOAD_PATHS || '/api/search')
    .split(',').map((p) => p.trim()).filter(Boolean),
};
