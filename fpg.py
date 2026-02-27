#!/usr/bin/env python
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import graphviz


@dataclass
class ModuleGraphEdge:
    source: str = field(default_factory=str)
    path: str = field(default_factory=str)
    option: str = field(default_factory=str)

    def __init__(self, entry: dict) -> None:
        source_path, _, path_and_option = str(entry["file"]).partition("-source")
        self.source = source_path.rsplit("/", 1)[-1]
        path_and_option = path_and_option.removeprefix("/")
        if ", " in path_and_option:
            self.path, _, self.option = path_and_option.partition(", ")
        else:
            self.path = path_and_option
            self.option = ""

    def to_dict(self):
        return {"source": self.source, "path": self.path}

    def __eq__(self, other: object):
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented
        return self.source == other.source and self.path == other.path


@dataclass
class ModuleGraphNode(ModuleGraphEdge):
    imports: list[ModuleGraphEdge] = field(default_factory=list)

    def to_dict(self):
        return (
            super().to_dict()
            | {"imports": [module.to_dict() for module in self.imports]}
            | ({"option": self.option} if self.option else {})
        )

    def __eq__(self, other: object):
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented
        return self.source == other.source and self.path == other.path


class ModuleGraph:
    modules: dict[tuple[str, str], ModuleGraphNode]

    def __init__(self, data: list) -> None:
        """Build a ModuleGraph from the loaded JSON data."""
        self.modules = {}
        for entry in data:
            self.process_entry(entry)

    def process_entry(self, entry: dict, parent: ModuleGraphNode | None = None) -> None:
        """Process a single entry from the graph JSON and add it to the ModuleGraph."""
        edge = ModuleGraphEdge(entry)
        node = self.get_or_create_module(edge)

        if parent is not None and edge != parent:
            self.add_import_to_module(parent, edge)

        imports = entry.get("imports", [])
        for imported_entry in imports:
            self.process_entry(imported_entry, node)

    def get_or_create_module(self, edge: ModuleGraphEdge) -> ModuleGraphNode:
        key = (edge.source, edge.path)
        if key not in self.modules:
            node = ModuleGraphNode(edge.source, edge.path, edge.option)
            self.modules[key] = node
        return self.modules[key]

    def add_import_to_module(self, parent: ModuleGraphNode, edge: ModuleGraphEdge):
        key = (parent.source, parent.path)
        if edge not in self.modules[key].imports:
            self.modules[key].imports.append(edge)

    def to_json(self) -> str:
        result = []
        for key in self.modules:
            result.append(self.modules[key].to_dict())
        return json.dumps(result, indent=2)

    def to_gv(self) -> graphviz.Digraph:
        dot = graphviz.Digraph("ModuleGraph")
        dot.attr("node", shape="box", fontname="Helvetica")

        # Add nodes
        for (source, path), node in self.modules.items():
            node_id = f"{source}-{path}"
            label = f"<<B>{path}</B><BR/>{node.option}<BR/><I>{source}</I>>"
            dot.node(name=node_id, label=label)

        # Add edges
        for (source, path), node in self.modules.items():
            from_id = f"{source}-{path}"
            for imported_edge in node.imports:
                to_id = f"{imported_edge.source}-{imported_edge.path}"
                dot.edge(from_id, to_id)

        return dot


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

    return parser.parse_args()


def load_json(json_file: Path) -> dict:
    """Load and return data from a JSON file."""
    f = json_file.open()
    return json.load(f)


def main():
    args = parse_args()
    data = load_json(args.input)

    # Filter data to only handle everything under flake.nix
    data = [element for element in data if str(element["file"]).endswith("/flake.nix")]
    graph = ModuleGraph(data)

    if args.format == "gv":
        print(graph.to_gv())
    else:
        print(graph.to_json())


if __name__ == "__main__":
    main()
