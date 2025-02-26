FROM python:3.12

ENV POETRY_VERSION=2.0.1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local'

# Set environment variables for the agent
ENV PYTHONPATH=/ \
    PYTHONUNBUFFERED=1

WORKDIR /

# Copy only what we need first to leverage caching
COPY pyproject.toml poetry.lock Makefile ./

# Copy the entire project
COPY alphaswarm/ ./alphaswarm/
COPY examples/ ./examples/
COPY tests/ ./tests/
COPY config/ ./config/

# Install poetry and dependencies
RUN curl -sSL 'https://install.python-poetry.org' | python3 - \
    && poetry --version \
    && poetry install --no-interaction --no-ansi --no-root

# Install additional dependencies for blockchain interaction
RUN pip install web3 hexbytes

# Set entrypoint to run the price forecaster
ENTRYPOINT ["make", "run-price-forecaster"]

# Add simple healthcheck
HEALTHCHECK --interval=5s --timeout=30s --retries=3 CMD python -c "import sys; sys.exit(0)"
