#!/usr/bin/env python
"""nixoscope - Visualize NixOS module import graphs.

Reads a NixOS module graph from a JSON file (as produced by ``nixos-option``
or similar tooling) and renders it either as a Graphviz digraph (.gv), mermaid (.mm) or as
structured JSON.

Typical usage::

    nixoscope --input graph.json --format gv --option services
"""

import argparse
import json
from pathlib import Path

from .module_graph import ModuleGraph
from .visualizer import GraphvizVisualizer, JsonVisualizer, MermaidVisualizer

_VISUALIZERS = {
    "gv": GraphvizVisualizer(),
    "mm": MermaidVisualizer(),
    "json": JsonVisualizer(),
}


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(description="Input module graph from a JSON file.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("graph.json"),
        help="Path to the graph JSON file (default: graph.json)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["gv", "mm", "json"],
        default="gv",
        help="Output format (default: gv)",
    )
    parser.add_argument(
        "--option",
        type=str,
        default=None,
        help="Filter by option prefix",
    )

    return parser.parse_args()


def load_json(json_file: Path) -> dict:
    """Load and return the parsed contents of a JSON file."""
    f = json_file.open()
    return json.load(f)


def main() -> None:
    """Entry point: parse args, build the graph, and print the output."""
    args = parse_args()
    raw_modules = load_json(args.input)

    # Filter data to only handle everything under flake.nix
    raw_modules = [raw_module for raw_module in raw_modules if str(raw_module["file"]).endswith("/flake.nix")]
    graph = ModuleGraph(raw_modules, args.option)
    print(graph.render(_VISUALIZERS[args.format]))


if __name__ == "__main__":
    main()
