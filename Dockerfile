###############################################################################
# BindCraft MCP – Docker Image
#
# Multi-stage build:
#   1. builder  – installs all conda/pip dependencies
#   2. runtime  – minimal image with only what's needed to run
#
# Build (without proxy):
#   docker build -t bindcraft-mcp .
#
# Build (with proxy - recommended for China):
#   docker build --build-arg HTTP_PROXY=http://host.docker.internal:7890 \
#                --build-arg HTTPS_PROXY=http://host.docker.internal:7890 \
#                -t bindcraft-mcp .
#
# Run (GPU):
#   docker run --gpus all -it bindcraft-mcp
#
# Run (CPU-only):
#   docker run -it bindcraft-mcp
###############################################################################

# Proxy configuration (pass via --build-arg)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# ---------- Stage 1: builder ----------
FROM continuumio/miniconda3:24.7.1-0 AS builder

# Re-declare ARGs for this stage
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set environment variables for proxy in builder stage
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}
ENV no_proxy=${NO_PROXY}

RUN apt-get update && apt-get install -y \
    git gcc g++ wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configure conda to use USTC mirror (China)
RUN mkdir -p /root/.conda && \
    printf 'channels:\n  - https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge/\nshow_channel_urls: true\n' > /root/.condarc && \
    conda clean -i

# Create conda environment with all dependencies
RUN conda create -p /env python=3.10 -y

# Install core conda packages
RUN conda install -p /env \
    pip pandas matplotlib 'numpy<2.0.0' biopython scipy seaborn \
    libgfortran5 tqdm ffmpeg fsspec \
    -c conda-forge -y

# Install ML packages
RUN conda install -p /env \
    chex dm-haiku 'flax<0.10.0' dm-tree joblib ml-collections immutabledict optax \
    -c conda-forge -y

# Configure pip to use USTC mirror and install JAX with CUDA 12 support
RUN /env/bin/pip config set global.index-url https://mirrors.ustc.edu.cn/pypi/simple && \
    /env/bin/pip install --no-cache-dir 'jax[cuda12]>=0.4,<=0.6.0'

# Install PyRosetta (may fail without license – non-fatal)
RUN conda install -p /env pyrosetta pdbfixer \
    --channel https://conda.graylab.jhu.edu -c conda-forge -y 2>/dev/null || true

# Install pip packages (using USTC mirror configured above)
RUN /env/bin/pip install --no-cache-dir fastmcp==2.13.1 loguru click
RUN /env/bin/pip install --no-cache-dir git+https://github.com/sokrypton/ColabDesign.git --no-deps || true

# Clean conda cache
RUN conda clean -a -y

# ---------- Stage 2: runtime ----------
FROM continuumio/miniconda3:24.7.1-0 AS runtime

# Re-declare ARGs for this stage
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# Set environment variables for proxy in runtime stage
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
ENV http_proxy=${HTTP_PROXY}
ENV https_proxy=${HTTPS_PROXY}
ENV no_proxy=${NO_PROXY}

RUN apt-get update && apt-get install -y \
    libgomp1 libgfortran5 git wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy conda environment from builder
COPY --from=builder /env /env

# Copy source code
COPY src/ ./src/
COPY clean_scripts/ ./clean_scripts/
COPY configs/ ./configs/

# Create directories for runtime
RUN mkdir -p tmp/inputs tmp/outputs jobs results repo/scripts/params repo/scripts/functions

# Clone BindCraft repository and set up scripts
RUN mkdir -p repo && \
    for attempt in 1 2 3; do \
      echo "Clone attempt $attempt/3"; \
      git clone --depth 1 https://github.com/martinpacesa/BindCraft repo/BindCraft && break; \
      if [ $attempt -lt 3 ]; then sleep 5; fi; \
    done \
    && cp repo/BindCraft/bindcraft.py repo/scripts/run_bindcraft.py \
    && cp -r repo/BindCraft/functions/* repo/scripts/functions/ 2>/dev/null || true \
    && chmod +x repo/scripts/functions/dssp repo/scripts/functions/DAlphaBall.gcc 2>/dev/null || true

# Download AlphaFold2 weights into the image (~5.3 GB)
RUN wget -q https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar \
        -O /app/repo/scripts/params/alphafold_params.tar \
    && tar -xf /app/repo/scripts/params/alphafold_params.tar -C /app/repo/scripts/params/ \
    && rm -f /app/repo/scripts/params/alphafold_params.tar

# Symlink so MCP tools can find scripts at /app/scripts
RUN ln -s /app/repo/scripts /app/scripts

# Copy examples (needed for default filter/advanced settings)
COPY examples/ ./examples/

# Make /app directory readable and writable by all users (for non-root execution)
RUN chmod -R 755 /app && \
    chmod -R 777 /app/tmp /app/jobs /app/results

# Configure cache directories for non-root users (fixes matplotlib/fontconfig permission errors)
# When running as non-root user (--user flag), tools can't write to /.config or /.cache
RUN mkdir -p /app/.cache /app/.config /app/.fontconfig && \
    chmod -R 777 /app/.cache /app/.config /app/.fontconfig

ENV PYTHONPATH=/app/src:/app/clean_scripts
ENV PATH=/env/bin:$PATH

# Configure cache directories for Python tools (matplotlib, fontconfig, etc.)
# These prevent "Permission denied" errors when running as non-root
ENV HOME=/app
ENV MPLCONFIGDIR=/app/.config/matplotlib
ENV XDG_CACHE_HOME=/app/.cache
ENV FONTCONFIG_PATH=/app/.fontconfig

# Enable GPU access for NVIDIA Container Toolkit
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Reset proxy environment variables (don't carry proxy into runtime)
ENV HTTP_PROXY=
ENV HTTPS_PROXY=
ENV NO_PROXY=
ENV http_proxy=
ENV https_proxy=
ENV no_proxy=

# Allow any UID to resolve via NSS (fixes getpwuid KeyError for --user flag)
RUN chmod 666 /etc/passwd
# Create entrypoint that adds the runtime UID to /etc/passwd if missing
RUN printf '#!/bin/bash\nif ! whoami &>/dev/null; then\n  echo "appuser:x:$(id -u):$(id -g)::/app:/bin/bash" >> /etc/passwd\nfi\nexec "$@"\n' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "src/bindcraft_mcp.py"]
