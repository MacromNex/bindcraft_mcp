#!/usr/bin/env python3
"""
Script: use_case_4_batch_design.py
Description: Process multiple protein binder design jobs in batch mode

Original Use Case: examples/use_case_4_batch_design.py
Dependencies Removed: Inlined MCP decorators and framework dependencies

Usage:
    python clean_scripts/use_case_4_batch_design.py --input <pdb_file_or_dir> --output <output_dir>

Example:
    python clean_scripts/use_case_4_batch_design.py --input examples/data/PDL1.pdb --output results/batch_jobs
"""

# ==============================================================================
# Minimal Imports (only essential packages)
# ==============================================================================
import argparse
import json
import subprocess
import sys
import os
import time
from pathlib import Path
from typing import Union, Optional, Dict, Any, List

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
DEFAULT_BATCH_CONFIG = {
    **DEFAULT_CONFIG,
    "base_name": "BatchBinder",
    "num_designs": 2,
    "hotspot": None,
    "chains": "A",
    "binder_length": 130,
    "filters_enabled": True,
    "max_concurrent": 1,  # Number of concurrent jobs
    "monitor_interval": 60  # Monitoring interval in seconds
}

# ==============================================================================
# Core Functions (main logic extracted from use case)
# ==============================================================================
def find_pdb_files(input_path: Path) -> List[Path]:
    """Find all PDB files in input path (file or directory)."""
    if input_path.is_file():
        if input_path.suffix.lower() == '.pdb':
            return [input_path]
        else:
            raise ValueError(f"Input file must be a PDB file: {input_path}")
    elif input_path.is_dir():
        pdb_files = list(input_path.glob("*.pdb"))
        if not pdb_files:
            raise ValueError(f"No PDB files found in directory: {input_path}")
        return sorted(pdb_files)
    else:
        raise FileNotFoundError(f"Input path not found: {input_path}")


def generate_target_settings(
    target_pdb: str,
    output_dir: str,
    name: str = "BatchBinder",
    chains: str = "A",
    hotspot: Optional[str] = None,
    binder_length: int = 130,
    num_designs: int = 2
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


def submit_single_job(
    pdb_file: Path,
    base_output_dir: Path,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Submit a single BindCraft job."""
    # Create job-specific name and output directory
    job_name = f"{config['base_name']}_{pdb_file.stem}"
    job_output_dir = base_output_dir / job_name
    job_output_dir = ensure_directory(job_output_dir)

    try:
        # Get BindCraft paths
        bindcraft_path = get_bindcraft_path()
        defaults = get_default_settings_paths()

        # Generate target settings
        target_settings = generate_target_settings(
            target_pdb=str(pdb_file),
            output_dir=str(job_output_dir),
            name=job_name,
            chains=config["chains"],
            hotspot=config.get("hotspot"),
            binder_length=config["binder_length"],
            num_designs=config["num_designs"]
        )

        # Save settings to file
        settings_file = job_output_dir / "target_settings.json"
        save_json(target_settings, settings_file)

        # Get absolute path to settings file
        settings_file_abs = str(settings_file.resolve())

        # Prepare command
        filters_json = defaults["filters"] if config["filters_enabled"] else None
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

        # Set up environment
        device = config.get("device", "0")
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(device)

        # Create log file for the background process
        log_file = job_output_dir / "bindcraft_run.log"

        print(f"   Submitting: {pdb_file.name} -> {job_name}")
        print(f"   Output: {job_output_dir}")
        print(f"   Log: {log_file}")

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

        return {
            "success": True,
            "job_name": job_name,
            "pdb_file": str(pdb_file),
            "output_dir": str(job_output_dir),
            "settings_file": str(settings_file),
            "log_file": str(log_file),
            "pid": process.pid,
            "status": "submitted",
            "device": device
        }

    except Exception as e:
        return {
            "success": False,
            "job_name": job_name,
            "pdb_file": str(pdb_file),
            "error": str(e),
            "status": "failed"
        }


def run_batch_design(
    input_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Main function for batch protein binder design processing.

    Args:
        input_file: Path to PDB file or directory containing PDB files
        output_file: Path to base output directory (optional)
        config: Configuration dict (uses DEFAULT_BATCH_CONFIG if not provided)
        **kwargs: Override specific config parameters

    Returns:
        Dict containing:
            - result: Batch processing results and job information
            - output_dir: Path to base output directory
            - metadata: Execution metadata

    Example:
        >>> result = run_batch_design("targets/", "batch_results/")
        >>> print(f"Jobs submitted: {len(result['result']['jobs'])}")
    """
    # Setup
    input_path = Path(input_file)
    final_config = {**DEFAULT_BATCH_CONFIG, **(config or {}), **kwargs}

    # Find PDB files
    try:
        pdb_files = find_pdb_files(input_path)
    except Exception as e:
        return {
            "success": False,
            "error": f"Error finding PDB files: {str(e)}"
        }

    # Determine output directory
    if output_file:
        output_dir = Path(output_file)
    else:
        output_dir = Path(f"results/{final_config['base_name']}_batch")

    output_dir = ensure_directory(output_dir)

    print(f"🚀 Starting batch processing...")
    print(f"   Input: {input_path}")
    print(f"   PDB files found: {len(pdb_files)}")
    print(f"   Output directory: {output_dir}")
    print(f"   Designs per target: {final_config['num_designs']}")
    print(f"   Device: GPU {final_config.get('device', '0')}")

    # Submit jobs
    jobs = []
    successful_jobs = 0
    failed_jobs = 0

    for pdb_file in pdb_files:
        job_result = submit_single_job(pdb_file, output_dir, final_config)
        jobs.append(job_result)

        if job_result["success"]:
            successful_jobs += 1
        else:
            failed_jobs += 1
            print(f"   ❌ Failed to submit {pdb_file.name}: {job_result['error']}")

    # Save batch tracking information
    batch_info = {
        "batch_id": f"batch_{int(time.time())}",
        "input_path": str(input_path),
        "output_directory": str(output_dir),
        "config": final_config,
        "total_targets": len(pdb_files),
        "successful_submissions": successful_jobs,
        "failed_submissions": failed_jobs,
        "jobs": jobs,
        "submission_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    batch_file = output_dir / "batch_jobs.json"
    save_json(batch_info, batch_file)

    print(f"\n📊 Batch submission complete:")
    print(f"   Total targets: {len(pdb_files)}")
    print(f"   Successful submissions: {successful_jobs}")
    print(f"   Failed submissions: {failed_jobs}")
    print(f"   Batch info saved: {batch_file}")

    if successful_jobs > 0:
        print(f"\n🔍 Monitor progress with:")
        for job in jobs:
            if job["success"]:
                print(f"   python clean_scripts/use_case_3_monitor_progress.py --output {job['output_dir']}")

    return {
        "success": successful_jobs > 0,
        "result": batch_info,
        "output_dir": str(output_dir),
        "batch_file": str(batch_file),
        "metadata": {
            "input_path": str(input_path),
            "config": final_config,
            "processing_time": "Batch submission completed"
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
    parser.add_argument('--input', '-i', required=True,
                       help='PDB file or directory containing PDB files')
    parser.add_argument('--output', '-o', help='Base output directory path')
    parser.add_argument('--base-name', default='BatchBinder',
                       help='Base name for binder designs (default: BatchBinder)')
    parser.add_argument('--chains', default='A', help='Target chains (default: A)')
    parser.add_argument('--hotspot', help='Hotspot residues (comma-separated)')
    parser.add_argument('--num-designs', type=int, default=2,
                       help='Number of designs per target (default: 2)')
    parser.add_argument('--binder-length', type=int, default=130,
                       help='Binder length (default: 130)')
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
        "base_name": args.base_name,
        "chains": args.chains,
        "hotspot": args.hotspot,
        "num_designs": args.num_designs,
        "binder_length": args.binder_length,
        "device": args.device,
        "filters_enabled": not args.no_filters
    })

    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}

    # Run batch design
    result = run_batch_design(
        input_file=args.input,
        output_file=args.output,
        config=config
    )

    if result["success"]:
        batch_info = result["result"]
        print(f"\n✅ Batch processing initiated successfully!")
        print(f"   Batch ID: {batch_info['batch_id']}")
        print(f"   Output directory: {result['output_dir']}")
        print(f"   Batch tracking file: {result['batch_file']}")
        print(f"   Successful jobs: {batch_info['successful_submissions']}/{batch_info['total_targets']}")
    else:
        print(f"\n❌ Batch processing failed: {result['error']}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())