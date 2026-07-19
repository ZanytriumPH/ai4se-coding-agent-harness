# Dockerfile — container distribution (通用要求 §3.2 任选其一).
#
# Primary distribution for this project is the PyPI wheel (see README §分发命令);
# this image is the optional container form. It builds a runnable image that:
#   - DEFAULT  : serves the WebUI on :8000 (a reachable WebUI interface, §5.9)
#   - `make demo`        : token-free three-act mechanism demo (guardrail/feedback/stop)
#   - `harness --run-webui --host 0.0.0.0 --workdir /workdir` : real-LLM browser HITL
#
# Credential hygiene (§3.1): the image NEVER bakes a key. A real-LLM run mounts
# the key via -e DEEPSEEK_API_KEY=... (env,明文 to the process — same threat
# model as .env; for production prefer the host keyring + `harness --init-key`
# inside a throwaway container). .env is .dockerignored so no plaintext key
# ships in a layer.

FROM python:3.11-slim

# keyring + any compiled C ext need gcc; make for the demo target.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Editable install so demo/, config.yaml, and webui static are live from the
# COPY'd tree; also installs the `harness` console script (pyproject [scripts]).
COPY . .
RUN pip install --no-cache-dir -e .[dev,llm]

# The repo the agent repairs. Mount your own broken repo over /workdir:
#   docker run -v /path/to/broken-repo:/workdir ...
RUN mkdir -p /workdir
ENV HARNESS_WORKDIR=/workdir

EXPOSE 8000

# Default: serve the WebUI frontend (stays up; a reachable interface).
# PORT-aware: cloud platforms (Render/Fly/Railway) inject PORT for web services
# (Render default 10000); fall back to 8000 for local `docker run`.
# Override for the token-free demo or a real-LLM driven run, see header comment.
CMD ["sh", "-c", "uvicorn webui.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
