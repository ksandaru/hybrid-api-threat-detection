FROM node:22-slim

WORKDIR /usr/src/app

# Dependencies are installed before the source is copied, so a source-only
# change does not invalidate the dependency layer. npm ci rather than install:
# it honours package-lock.json exactly, which is what makes the build
# reproducible.
COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

# The base image ships an unprivileged 'node' user. Running as root inside a
# container that terminates untrusted input would be a poor advertisement for a
# security dissertation.
USER node

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
  CMD node -e "require('http').get('http://localhost:3000/health',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
