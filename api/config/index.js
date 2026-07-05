require('dotenv').config();

module.exports = {
  port: parseInt(process.env.PORT, 10) || 3000,
  mlServiceUrl: process.env.ML_SERVICE_URL || 'http://localhost:8000',
  databaseUrl: process.env.DATABASE_URL,
  detectionThreshold: parseFloat(process.env.DETECTION_THRESHOLD) || 0.7,
  jwtSecret: process.env.JWT_SECRET || 'change-me-in-local-env',
};
