#!/usr/bin/env python
"""nixoscope - Visualize NixOS module import graphs.

Reads a NixOS module graph from a JSON file (as produced by ``nixos-option``
or similar tooling) and renders it either as a Graphviz digraph (.gv) or as
structured JSON.

Typical usage::

    nixoscope --input graph.json --format gv --option services
"""

import argparse
import colorsys
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import graphviz
import graphviz.encoding

_UNKNOWN_SOURCE: str = "<unknown-source>"
_UNKNOWN_MODULE: str = "<unknown-module>"
_UNKNOWN_FUNCTION_CHAIN: str = "<unknown-function-chain>"
_UNKNOWN_FUNCTION_CHAIN_REGEX: str = r"(__functor|includes|<function body>).*$"


@dataclass
class ModuleGraphEdge:
    """A directed edge representing a module import relationship.

    Parses a raw module entry from the graph JSON and extracts the Nix store
    source hash, the module file path relative to the store path, the option
    that triggered the import (if any), and a disambiguation key for anonymous
    modules whose file is reported as ``<unknown-file>``.

    Attributes:
        source: Nix store hash identifying the derivation that owns the module.
        module: File path of the module relative to its store path.
        key:    Hash-derived key used to disambiguate unknown-source entries.
        option: NixOS option that caused this module to be imported, or ``""``
                if the import was unconditional.

    """

    source: str
    module: str
    key: str
    option: str

    def __init__(self, raw_module: dict) -> None:
        """Parse a raw module dict into a typed edge.

        Handles two file formats emitted by NixOS evaluation:

        * Normal path: ``/nix/store/<hash>-source/<module>[, via option <opt>]``
        * Unknown file: ``<unknown-file>[, via option <opt>]``

        The ``, via option`` suffix is stripped and stored in :attr:`option`.
        Any unresolvable function chains in the option string are normalised to
        :data:`_UNKNOWN_FUNCTION_CHAIN`.
        """
        file = str(raw_module["file"])
        option = ""
        key = ""
        if file.startswith("<unknown-file>"):
            self.source = _UNKNOWN_SOURCE
            self.module = _UNKNOWN_MODULE
            _, _, option = file.partition(", via option ")
            key = str(abs(hash(raw_module["key"])))
        else:
            source, _, module_and_option = file.partition("-source")
            self.source = source.rsplit("/", 1)[-1]
            module_and_option = module_and_option.removeprefix("/")
            self.module, _, option = module_and_option.partition(", via option ")
        self.option = re.sub(_UNKNOWN_FUNCTION_CHAIN_REGEX, _UNKNOWN_FUNCTION_CHAIN, option)
        self.key = key

    def to_dict(self):
        """Serialise to a plain dict, omitting ``option`` when empty."""
        return {"source": self.source, "module": self.module, "key": self.key} | (
            {"option": self.option} if self.option else {}
        )

    def __eq__(self, other: object):
        """Two edges are equal when they point to the same source/module pair.

        For unknown-source entries the ``key`` is also compared because the
        module name is always ``<unknown-module>`` and therefore not unique.
        """
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented
        eq = self.source == other.source and self.module == other.module
        if _UNKNOWN_SOURCE in (self.source, other.source):
            return eq and self.key == other.key
        return eq


@dataclass
class ModuleGraphNode(ModuleGraphEdge):
    """A node in the module graph, extending :class:`ModuleGraphEdge` with its outgoing imports.

    Attributes:
        imports: Ordered list of edges to modules directly imported by this node.

    """

    imports: list[ModuleGraphEdge] = field(default_factory=list)

    def to_dict(self):
        """Serialise node and all its imports recursively to a plain dict."""
        return super().to_dict() | {"imports": [module.to_dict() for module in self.imports]}

    def __eq__(self, other: object):
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented

        eq = self.source == other.source and self.module == other.module
        if _UNKNOWN_SOURCE in (self.source, other.source):
            return eq and self.key == other.key
        return eq


class ModuleGraph:
    """A graph of NixOS modules and their import relationships.

    Nodes are keyed by ``(source, module, key)`` tuples. When an
    ``option_filter`` is provided, only nodes whose triggering option starts
    with that prefix are included; filtered-out nodes are transparently skipped
    and their children are reparented to the nearest retained ancestor.

    Attributes:
        modules: Mapping from ``(source, module, key)`` to :class:`ModuleGraphNode`.

    """

    modules: dict[tuple[str, str, str], ModuleGraphNode]

    def __init__(self, raw_modules: list, option_filter: str | None) -> None:
        """Build a ModuleGraph from the loaded JSON data.

        Args:
            raw_modules:   List of raw module dicts loaded from the graph JSON.
            option_filter: Optional NixOS option prefix used to restrict which
                           modules are included in the graph.

        """
        self.modules = {}
        for raw_module in raw_modules:
            self._process_entry(raw_module, option_filter=option_filter)

    def _process_entry(
        self,
        raw_module: dict,
        option_filter: str | None,
        parent: ModuleGraphNode | None = None,
    ) -> None:
        """Recursively process a module entry and add it to the graph.

        A node is included when it is the ``flake.nix`` entry point or its
        option matches the filter prefix. Excluded nodes are skipped but their
        children are still traversed using the last retained ancestor as parent,
        effectively reparenting them.
        """
        edge = ModuleGraphEdge(raw_module)

        # Check if flake.nix starting point
        is_flake_entry = edge.module == "flake.nix"
        # Check if option filter should be applied and if this edge matches the option filter
        matches_option_filter = option_filter is None or edge.option.startswith(option_filter)

        if is_flake_entry or matches_option_filter:
            node = self._get_or_create_module(edge)
            if parent and edge != parent:
                self._add_import_to_module(parent, edge)
        else:
            node = parent

        # Always process imports recursively
        imports = raw_module.get("imports", [])
        for imported_entry in imports:
            self._process_entry(imported_entry, option_filter, node)

    def _get_or_create_module(self, edge: ModuleGraphEdge) -> ModuleGraphNode:
        """Return the existing node for ``edge``, creating it if necessary."""
        key = (edge.source, edge.module, edge.key)
        if key not in self.modules:
            node = ModuleGraphNode(edge.source, edge.module, edge.key, edge.option)
            self.modules[key] = node
        return self.modules[key]

    def _add_import_to_module(self, parent: ModuleGraphNode, edge: ModuleGraphEdge) -> None:
        """Append ``edge`` to ``parent``'s import list, avoiding duplicates."""
        key = (parent.source, parent.module, parent.key)
        if edge not in self.modules[key].imports:
            self.modules[key].imports.append(edge)

    def to_json(self) -> str:
        """Serialise the graph to a JSON string."""
        result = [module.to_dict() for module in self.modules.values()]
        return json.dumps(result, indent=2)

    def to_gv(self) -> graphviz.Digraph:
        """Render the graph as a Graphviz :class:`~graphviz.Digraph`.

        Each node is labelled with the module filename, its triggering option
        (if any), and the source hash. Nodes from the same derivation share a
        background colour derived from the source hash.
        """
        dot = graphviz.Digraph("ModuleGraph")
        dot.attr("node", shape="box", fontname="Helvetica", style="filled")

        # Add nodes
        for (source, module, key), node in self.modules.items():
            node_id = graphviz.escape(f"{source}-{module}")
            if source == _UNKNOWN_SOURCE:
                node_id = graphviz.escape(f"{node_id}-{key}")
            label = f"<<B>{html.escape(module)}</B><BR/>{html.escape(node.option)}<BR/><I>{html.escape(source)}</I>>"
            dot.node(name=node_id, label=label, fillcolor=ModuleGraph._color_from_cluster_id(source))

        # Add edges
        for (source, module, key), node in self.modules.items():
            from_id = graphviz.escape(f"{source}-{module}")
            if source == _UNKNOWN_SOURCE:
                from_id = graphviz.escape(f"{from_id}-{key}")
            for edge in node.imports:
                to_id = graphviz.escape(f"{edge.source}-{edge.module}")
                if edge.source == _UNKNOWN_SOURCE:
                    to_id = graphviz.escape(f"{to_id}-{edge.key}")
                dot.edge(from_id, to_id)

        return dot

    @staticmethod
    def _color_from_cluster_id(cluster_id: str) -> str:
        """Derive a stable pastel hex colour from ``cluster_id``.

        Uses a golden-angle hue step so that adjacent hash values produce
        visually distinct colours.
        """
        n = abs(hash(cluster_id))
        # Use 137 as golden angle to create different colors even if two n are close in range
        hue = (n * 137) % 360
        saturation = 0.5  # not too grey, not too vivid
        lightness = 0.80  # high = washed out / soft
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, saturation)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


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
        choices=["gv", "json"],
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

    if args.format == "gv":
        print(graph.to_gv())
    else:
        print(graph.to_json())


if __name__ == "__main__":
    main()
