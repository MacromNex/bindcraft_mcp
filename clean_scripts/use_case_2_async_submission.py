#!/usr/bin/env python3
"""
Script: use_case_2_async_submission.py
Description: Submit protein binder design jobs asynchronously (background execution)

Original Use Case: examples/use_case_2_async_submission.py
Dependencies Removed: Inlined MCP decorators and framework dependencies

Usage:
    python clean_scripts/use_case_2_async_submission.py --input <pdb_file> --output <output_dir>

Example:
    python clean_scripts/use_case_2_async_submission.py --input examples/data/PDL1.pdb --output results/async_job
"""

# ==============================================================================
# Minimal Imports (only essential packages)
# ==============================================================================
import argparse
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Union, Optional, Dict, Any

# Add lib to path for shared utilities
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from lib.io import load_json, save_json, resolve_path, ensure_directory
from lib.bindcraft import (
    get_bindcraft_path, get_default_settings_paths, DEFAULT_CONFIG
)

# ==============================================================================
# Configuration (extracted from use case)
# ==============================================================================
DEFAULT_ASYNC_CONFIG = {
    **DEFAULT_CONFIG,
    "name": "AsyncBinder",
    "num_designs": 3,
    "hotspot": None,
    "chains": "A",
    "binder_length": 130,
    "filters_enabled": True
}

# ==============================================================================
# Core Function (main logic extracted from use case)
# ==============================================================================
def generate_target_settings(
    target_pdb: str,
    output_dir: str,
    name: str = "AsyncBinder",
    chains: str = "A",
    hotspot: Optional[str] = None,
    binder_length: int = 130,
    num_designs: int = 3
) -> Dict[str, Any]:
    """Generate target settings JSON for BindCraft in correct format.

    Returns settings in the format expected by run_bindcraft.py:
    - design_path: Output directory for designed binders
    - binder_name: Prefix name for designed binders
    - starting_pdb: Target protein PDB structure
    - chains: Target chain(s) to design binder against
    - target_hotspot_residues: Residue numbers to target (comma-separated)
    - lengths: [min_length, max_length] range for binder length
    - number_of_final_designs: Target number of accepted designs
    """
    target_pdb_abs = resolve_path(target_pdb)
    output_dir_abs = resolve_path(output_dir)

    settings = {
        "design_path": output_dir_abs,                    # NOT "output_dir"
        "binder_name": name,
        "starting_pdb": target_pdb_abs,                   # NOT "target_pdb"
        "chains": chains,                                  # NOT "target_chains"
        "target_hotspot_residues": hotspot if hotspot else "",  # NOT "hotspot"
        "lengths": [binder_length, binder_length],        # Array format, NOT single int
        "number_of_final_designs": num_designs            # NOT "num_designs"
    }

    return settings


def run_async_submission(
    input_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Main function for async protein binder design submission.

    Args:
        input_file: Path to target PDB file
        output_file: Path to output directory (optional)
        config: Configuration dict (uses DEFAULT_ASYNC_CONFIG if not provided)
        **kwargs: Override specific config parameters

    Returns:
        Dict containing:
            - result: Submission status and job info
            - output_dir: Path to output directory
            - metadata: Execution metadata

    Example:
        >>> result = run_async_submission("target.pdb", "output_dir")
        >>> print(f"Job status: {result['result']['status']}")
    """
    # Setup
    input_file = Path(input_file)
    final_config = {**DEFAULT_ASYNC_CONFIG, **(config or {}), **kwargs}

    if not input_file.exists():
        raise FileNotFoundError(f"Input PDB file not found: {input_file}")

    # Determine output directory
    if output_file:
        output_dir = Path(output_file)
    else:
        output_dir = Path(f"results/{final_config['name']}_async")

    output_dir = ensure_directory(output_dir)

    try:
        # Get BindCraft paths
        bindcraft_path = get_bindcraft_path()
        defaults = get_default_settings_paths()

        # Generate target settings
        target_settings = generate_target_settings(
            target_pdb=str(input_file),
            output_dir=str(output_dir),
            name=final_config["name"],
            chains=final_config["chains"],
            hotspot=final_config.get("hotspot"),
            binder_length=final_config["binder_length"],
            num_designs=final_config["num_designs"]
        )

        # Save settings to file
        settings_file = output_dir / "target_settings.json"
        save_json(target_settings, settings_file)

        # Get absolute path to settings file
        settings_file_abs = str(settings_file.resolve())

        # Prepare command
        filters_json = defaults["filters"] if final_config["filters_enabled"] else None
        advanced_json = defaults["advanced"]

        cmd = [
            sys.executable,
            str(bindcraft_path / "run_bindcraft.py"),
            f"--settings={settings_file_abs}",
        ]

        if filters_json:
            cmd.append(f"--filters={filters_json}")
        if advanced_json:
            cmd.append(f"--advanced={advanced_json}")

        # Add device
        device = final_config.get("device", "0")

        print(f"🚀 Submitting BindCraft job asynchronously...")
        print(f"   Target: {input_file.name}")
        print(f"   Output: {output_dir}")
        print(f"   Designs: {final_config['num_designs']}")
        print(f"   Device: GPU {device}")

        # Set up environment
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(device)

        # Create log file for the background process
        log_file = output_dir / "bindcraft_run.log"

        # Submit job in background
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(bindcraft_path),
                start_new_session=True,  # Detach from parent
            )

        print(f"   Background process PID: {process.pid}")
        print(f"   Log file: {log_file}")
        print(f"   Monitor with: python clean_scripts/use_case_3_monitor_progress.py --output {output_dir}")

        return {
            "success": True,
            "result": {
                "status": "submitted",
                "message": "BindCraft job submitted successfully. Use use_case_3_monitor_progress.py to monitor.",
                "pid": process.pid,
                "log_file": str(log_file)
            },
            "output_dir": str(output_dir),
            "settings_file": str(settings_file),
            "metadata": {
                "input_file": str(input_file),
                "config": final_config,
                "submission_time": "Job submitted",
                "device_used": device
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Job submission failed: {str(e)}",
            "output_dir": str(output_dir) if 'output_dir' in locals() else None,
            "metadata": {
                "input_file": str(input_file),
                "config": final_config
            }
        }


# ==============================================================================
# CLI Interface
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--input', '-i', required=True, help='Target PDB file path')
    parser.add_argument('--output', '-o', help='Output directory path')
    parser.add_argument('--name', default='AsyncBinder', help='Binder name (default: AsyncBinder)')
    parser.add_argument('--chains', default='A', help='Target chains (default: A)')
    parser.add_argument('--hotspot', help='Hotspot residues (comma-separated)')
    parser.add_argument('--num-designs', type=int, default=3, help='Number of designs (default: 3)')
    parser.add_argument('--binder-length', type=int, default=130, help='Binder length (default: 130)')
    parser.add_argument('--device', default='0', help='GPU device (default: 0)')
    parser.add_argument('--config', '-c', help='Config file (JSON)')
    parser.add_argument('--no-filters', action='store_true', help='Disable filters')

    args = parser.parse_args()

    # Load config if provided
    config = {}
    if args.config:
        config = load_json(args.config)

    # Override with CLI args
    config.update({
        "name": args.name,
        "chains": args.chains,
        "hotspot": args.hotspot,
        "num_designs": args.num_designs,
        "binder_length": args.binder_length,
        "device": args.device,
        "filters_enabled": not args.no_filters
    })

    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}

    # Run async submission
    result = run_async_submission(
        input_file=args.input,
        output_file=args.output,
        config=config
    )

    if result["success"]:
        job_info = result["result"]
        print(f"\n✅ Job submitted successfully!")
        print(f"   Output directory: {result['output_dir']}")
        print(f"   Process ID: {job_info['pid']}")
        print(f"   Status: {job_info['status']}")
        print(f"   Log file: {job_info['log_file']}")
        print(f"\n🔍 To monitor progress:")
        print(f"   python clean_scripts/use_case_3_monitor_progress.py --output {result['output_dir']}")
    else:
        print(f"\n❌ Job submission failed: {result['error']}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())