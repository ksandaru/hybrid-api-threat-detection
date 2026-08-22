# The traffic simulator, containerised so a demonstrator needs only Docker --
# no host Python, no virtualenv. It runs on the same Compose network as the
# stack and reaches the API by service name.
#
# The working directory mirrors the repo layout (attack-sim/ under the project
# root) so that common.py resolves evaluation/traffic/ to /app/evaluation, which
# is bind-mounted back to the host in docker-compose.yml. That is what lets the
# recalibration step read the CSVs whether it runs in a container or on the host.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    API_URL=http://api:3000

WORKDIR /app/attack-sim

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default action runs every generator in order. Override on the command line to
# run one, e.g. `docker compose run --rm sim python sqli_attack.py`.
CMD ["python", "run_all.py"]
