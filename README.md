# BindCraft MCP

**Model Context Protocol (MCP) server for protein binder design using BindCraft via Docker**

Design high-affinity protein binders against target proteins using:
- **AF2 Hallucination** — Generate binder backbone conformations
- **MPNN Sequence Design** — Optimize amino acid sequences
- **AF2 Validation** — Predict and validate complex structures
- **PyRosetta Scoring** — Evaluate interface quality and energy

## Quick Start with Docker

### Approach 1: Pull Pre-built Image from GitHub

The fastest way to get started. A pre-built Docker image is automatically published to GitHub Container Registry on every release.

```bash
# Pull the latest image
docker pull ghcr.io/macromnex/bindcraft_mcp:latest

# Register with Claude Code (runs as current user to avoid permission issues)
claude mcp add bindcraft -- docker run -i --rm --user `id -u`:`id -g` --gpus all --ipc=host -v `pwd`:`pwd` ghcr.io/macromnex/bindcraft_mcp:latest
```

**Note:** Run from your project directory. `${pwd}` expands to the current working directory.

**Requirements:**
- Docker with GPU support (`nvidia-docker` or Docker with NVIDIA runtime)
- Claude Code installed

That's it! The BindCraft MCP server is now available in Claude Code.

---

### Approach 2: Build Docker Image Locally

Build the image yourself and install it into Claude Code. Useful for customization or offline environments.

```bash
# Clone the repository
git clone https://github.com/MacromNex/bindcraft_mcp.git
cd bindcraft_mcp

# Build the Docker image
docker build -t bindcraft_mcp:latest .

# Build with proxy (recommended for users in China)
docker build --build-arg HTTP_PROXY=http://host.docker.internal:7890 \
             --build-arg HTTPS_PROXY=http://host.docker.internal:7890 \
             -t bindcraft_mcp:latest .
```

**Note for users in China:** The Dockerfile is pre-configured to use USTC mirrors for both conda and pip, which significantly speeds up package downloads without requiring a proxy:
- **Conda**: `https://mirrors.ustc.edu.cn/anaconda/cloud/conda-forge`
- **PyPI**: `https://mirrors.ustc.edu.cn/pypi/simple`

```bash
# Build without proxy (uses USTC mirrors by default)
docker build -t bindcraft_mcp:latest .

# Register with Claude Code (runs as current user to avoid permission issues)
claude mcp add bindcraft -- docker run -i --rm --user `id -u`:`id -g` --gpus all --ipc=host -v `pwd`:`pwd` bindcraft_mcp:latest
```

**Note:** Run from your project directory. `${pwd}` expands to the current working directory.

**Requirements:**
- Docker with GPU support
- Claude Code installed
- Git (to clone the repository)

**About the Docker Flags:**
- `-i` — Interactive mode for Claude Code
- `--rm` — Automatically remove container after exit
- `--user ${id -u}:${id -g}` — Runs the container as your current user, so output files are owned by you (not root)
- `--gpus all` — Grants access to all available GPUs
- `--ipc=host` — Uses host IPC namespace for better performance
- `-v` — Mounts your project directory so the container can access your data

---

## Verify Installation

After adding the MCP server, you can verify it's working:

```bash
# List registered MCP servers
claude mcp list

# You should see 'bindcraft' in the output
```

In Claude Code, you can now use all 5 BindCraft tools:
- `bindcraft_design_binder` — Synchronous binder design
- `bindcraft_submit` — Async design job submission
- `bindcraft_check_status` — Monitor job progress
- `generate_config` — Auto-generate configurations from PDB
- `validate_config` — Validate configuration files

---

## Usage Examples

Once registered, you can use the BindCraft tools directly in Claude Code. Here are some common workflows:

### Example 1: Quick Binder Design

```
Design a binder against the target protein at /path/to/target.pdb. Use the bindcraft_design_binder tool with 3 designs, targeting chain A, with binder lengths between 65 and 150 residues.
```

### Example 2: Generate Configuration from PDB

```
I have a target protein at /path/to/target.pdb. Can you generate a configuration file using generate_config with detailed analysis? Target hotspot residues should be automatically identified.
```

### Example 3: Submit Async Design Job

```
Submit an async binder design job for the target at /path/to/target.pdb. Use bindcraft_submit with 10 designs, chain A, and output to /path/to/output/. Then monitor the job with bindcraft_check_status.
```

### Example 4: Validate Configuration File

```
I have a configuration file at /path/to/config.json. Can you validate it using validate_config to ensure all parameters are correct before running the design?
```

### Example 5: Batch Design with Auto Config

```
I have a target PDB at /path/to/target.pdb. First, generate an optimized config using generate_config, then submit an async design job with bindcraft_submit for 5 designs, and save results to /path/to/results/.
```

---

## Next Steps

- **Detailed documentation**: See [details.md](details.md) for comprehensive guides on:
  - Local Python script usage (5 use cases)
  - All available MCP tools and parameters
  - Example workflows and tutorials
  - Configuration options
  - Troubleshooting

- **Local Setup (Alternative to Docker)**: See [details.md](details.md#installation-details) for conda-based environment setup if you prefer to run locally without Docker.

---

## Key Features

✅ **Synchronous Design** — Fast results for single targets (1-10 minutes)
✅ **Async Processing** — Long-running jobs for complex designs (>10 minutes)
✅ **Batch Processing** — Process multiple targets concurrently
✅ **Job Management** — Complete lifecycle tracking and monitoring
✅ **Auto Config** — Generate optimized parameters from PDB files
✅ **GPU Acceleration** — Full CUDA and JAX/XLA support via Docker
✅ **Error Handling** — Robust error reporting and recovery

---

## GPU Support

Both Docker approaches fully support:
- Multi-GPU systems (all GPUs automatically available in container)
- Single GPU setup
- CPU-only inference (via `--gpus '""'` if needed)

---

## Troubleshooting

**Docker not found?**
```bash
docker --version  # Install Docker if missing
```

**GPU not accessible?**
- Ensure NVIDIA Docker runtime is installed
- Check with `docker run --gpus all ubuntu nvidia-smi`

**Claude Code not found?**
```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code
```

See [details.md](details.md#troubleshooting) for more troubleshooting guidance.

---

## License

Based on the original [BindCraft](https://github.com/martinpacesa/BindCraft) repository by Martin Pacesa and colleagues.
