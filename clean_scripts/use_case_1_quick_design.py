#!/usr/bin/env python3
"""
Script: use_case_1_quick_design.py
Description: Quick synchronous protein binder design from PDB structure

Original Use Case: examples/use_case_1_quick_design.py
Dependencies Removed: Inlined MCP decorators and framework dependencies

Usage:
    python clean_scripts/use_case_1_quick_design.py --input <pdb_file> --output <output_dir>

Example:
    python clean_scripts/use_case_1_quick_design.py --input examples/data/PDL1.pdb --output results/quick_design
"""

# ==============================================================================
# Minimal Imports (only essential packages)
# ==============================================================================
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Union, Optional, Dict, Any

# Add lib to path for shared utilities
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from lib.io import load_json, save_json, resolve_path, ensure_directory
from lib.bindcraft import (
    get_bindcraft_path, get_default_settings_paths, run_command, DEFAULT_CONFIG
)

# ==============================================================================
# Configuration (extracted from use case)
# ==============================================================================
DEFAULT_DESIGN_CONFIG = {
    **DEFAULT_CONFIG,
    "name": "Binder",
    "num_designs": 1,
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
    name: str = "Binder",
    chains: str = "A",
    hotspot: Optional[str] = None,
    binder_length: int = 130,
    num_designs: int = 1
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


def collect_design_statistics(output_dir: Path) -> Dict[str, Any]:
    """Collect statistics from BindCraft output."""
    stats = {
        "total_designs": 0,
        "accepted_designs": 0,
        "rejected_designs": 0,
        "accepted_files": [],
        "rejected_files": []
    }

    # Count accepted designs
    accepted_dir = output_dir / "Accepted"
    if accepted_dir.exists():
        accepted_files = list(accepted_dir.glob("*.pdb"))
        stats["accepted_designs"] = len(accepted_files)
        stats["accepted_files"] = [str(f.name) for f in accepted_files]

    # Count rejected designs
    rejected_dir = output_dir / "Rejected"
    if rejected_dir.exists():
        rejected_files = list(rejected_dir.glob("*.pdb"))
        stats["rejected_designs"] = len(rejected_files)
        stats["rejected_files"] = [str(f.name) for f in rejected_files]

    stats["total_designs"] = stats["accepted_designs"] + stats["rejected_designs"]

    return stats


def run_quick_design(
    input_file: Union[str, Path],
    output_file: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Main function for quick protein binder design.

    Args:
        input_file: Path to target PDB file
        output_file: Path to save output directory (optional)
        config: Configuration dict (uses DEFAULT_DESIGN_CONFIG if not provided)
        **kwargs: Override specific config parameters

    Returns:
        Dict containing:
            - result: Design statistics and results
            - output_dir: Path to output directory
            - metadata: Execution metadata

    Example:
        >>> result = run_quick_design("target.pdb", "output_dir")
        >>> print(f"Accepted: {result['result']['accepted_designs']}")
    """
    # Setup
    input_file = Path(input_file)
    final_config = {**DEFAULT_DESIGN_CONFIG, **(config or {}), **kwargs}

    if not input_file.exists():
        raise FileNotFoundError(f"Input PDB file not found: {input_file}")

    # Determine output directory
    if output_file:
        output_dir = Path(output_file)
    else:
        output_dir = Path(f"results/{final_config['name']}_quick_design")

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

        print(f"🚀 Starting BindCraft design pipeline...")
        print(f"   Target: {input_file.name}")
        print(f"   Output: {output_dir}")
        print(f"   Designs: {final_config['num_designs']}")
        print(f"   Device: GPU {device}")

        # Run design
        result = run_command(cmd, device=device, cwd=str(bindcraft_path))

        if not result["success"]:
            return {
                "success": False,
                "error": f"BindCraft execution failed: {result.get('logs', ['Unknown error'])}",
                "output_dir": str(output_dir),
                "metadata": {
                    "input_file": str(input_file),
                    "config": final_config,
                    "command": result.get("command")
                }
            }

        # Collect output statistics
        stats = collect_design_statistics(output_dir)

        return {
            "success": True,
            "result": stats,
            "output_dir": str(output_dir),
            "settings_file": str(settings_file),
            "metadata": {
                "input_file": str(input_file),
                "config": final_config,
                "execution_time": "See logs for timing",
                "device_used": device
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Design execution failed: {str(e)}",
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
    parser.add_argument('--name', default='Binder', help='Binder name (default: Binder)')
    parser.add_argument('--chains', default='A', help='Target chains (default: A)')
    parser.add_argument('--hotspot', help='Hotspot residues (comma-separated)')
    parser.add_argument('--num-designs', type=int, default=1, help='Number of designs (default: 1)')
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

    # Run design
    result = run_quick_design(
        input_file=args.input,
        output_file=args.output,
        config=config
    )

    if result["success"]:
        stats = result["result"]
        print(f"\n✅ Design completed successfully!")
        print(f"   Output directory: {result['output_dir']}")
        print(f"   Total designs: {stats['total_designs']}")
        print(f"   Accepted: {stats['accepted_designs']}")
        print(f"   Rejected: {stats['rejected_designs']}")
        if stats['accepted_files']:
            print(f"   Accepted files: {', '.join(stats['accepted_files'])}")
    else:
        print(f"\n❌ Design failed: {result['error']}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())