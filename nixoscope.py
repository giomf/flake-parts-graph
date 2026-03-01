#!/usr/bin/env python
import argparse
import colorsys
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import graphviz
import graphviz.encoding

_UNKNOWN_MODULE: str = "<unknown-module>"
_UNKNOWN_SOURCE: str = "<unknown-source>"
_UNKNOWN_FUNCTION_CHAIN: str = "<unknown-function-chain>"
_UNKNOWN_FUNCTION_CHAIN_REGEX: str = r"(__functor|includes|<function body>).*$"


@dataclass
class ModuleGraphEdge:
    source: str
    module: str
    key: str
    option: str

    def __init__(self, raw_module: dict) -> None:
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
        return {"source": self.source, "module": self.module, "key": self.key} | (
            {"option": self.option} if self.option else {}
        )

    def __eq__(self, other: object):
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented
        eq = self.source == other.source and self.module == other.module
        if _UNKNOWN_SOURCE in (self.source, other.source):
            return eq and self.key == other.key
        return eq


@dataclass
class ModuleGraphNode(ModuleGraphEdge):
    imports: list[ModuleGraphEdge] = field(default_factory=list)

    def gv_id(self) -> str:
        return str(hash(self.source + self.module + self.key))

    def to_dict(self):
        return super().to_dict() | {"imports": [module.to_dict() for module in self.imports]}

    def __eq__(self, other: object):
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented

        eq = self.source == other.source and self.module == other.module
        if _UNKNOWN_SOURCE in (self.source, other.source):
            return eq and self.key == other.key
        return eq


class ModuleGraph:
    modules: dict[tuple[str, str, str], ModuleGraphNode]

    def __init__(self, raw_modules: list, option_filter: str | None) -> None:
        """Build a ModuleGraph from the loaded JSON data."""
        self.modules = {}
        for raw_module in raw_modules:
            self._process_entry(raw_module, option_filter=option_filter)

    def _process_entry(
        self,
        raw_module: dict,
        option_filter: str | None,
        parent: ModuleGraphNode | None = None,
    ) -> None:
        """Process a single entry from the graph JSON and add it to the ModuleGraph."""
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
        key = (edge.source, edge.module, edge.key)

        if key not in self.modules:
            node = ModuleGraphNode(edge.source, edge.module, edge.key, edge.option)
            self.modules[key] = node
        return self.modules[key]

    def _add_import_to_module(self, parent: ModuleGraphNode, edge: ModuleGraphEdge) -> None:
        key = (parent.source, parent.module, parent.key)
        if edge not in self.modules[key].imports:
            self.modules[key].imports.append(edge)

    def to_json(self) -> str:
        result = [module.to_dict() for module in self.modules.values()]
        return json.dumps(result, indent=2)

    def to_gv(self) -> graphviz.Digraph:
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

        # Hash the string to a number
        n = abs(hash(cluster_id))
        # Use 137 as golden angle to create different colors even if two n are close in range
        hue = (n * 137) % 360
        saturation = 0.5  # not too grey, not too vivid
        lightness = 0.80  # high = washed out / soft
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, saturation)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def parse_args() -> argparse.Namespace:
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
    """Load and return data from a JSON file."""
    f = json_file.open()
    return json.load(f)


def main():
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
