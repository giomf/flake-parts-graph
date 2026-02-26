#!/usr/bin/env python
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModuleNode:
    source: str = field(default_factory=str)
    imports: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class ModuleGraphEdge:
    source: str = field(default_factory=str)
    path: str = field(default_factory=str)

    def __init__(self, entry: dict) -> None:
        parts = str(entry["file"]).split("-source")
        self.source = parts[0].rsplit("/", 1)[-1]
        self.path = parts[-1].removeprefix("/")

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
        return super().to_dict() | {"imports": [module.to_dict() for module in self.imports]}

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
            node = ModuleGraphNode(edge.source, edge.path)
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

    def to_graphviz(self) -> str:
        lines = ["digraph ModuleGraph {", '\tnode [shape=box fontname="Helvetica"]']
        for (source, path), _ in self.modules.items():
            node_id = f"{source}:{path}"
            escaped_id = node_id.replace('"', '\\"')
            escaped_path = path.replace('"', '\\"')
            escaped_source = source.replace('"', '\\"')
            # HTML-like label: path bold on top, source italic below
            label = f"<<B>{escaped_path}</B><BR/><I>{escaped_source}</I>>"
            lines.append(f'\t"{escaped_id}" [label={label}];')
        for (source, path), node in self.modules.items():
            from_id = f"{source}:{path}"
            escaped_from = from_id.replace('"', '\\"')
            for imported_edge in node.imports:
                to_id = f"{imported_edge.source}:{imported_edge.path}"
                escaped_to = to_id.replace('"', '\\"')
                lines.append(f'\t"{escaped_from}" -> "{escaped_to}";')
        lines.append("}")
        return "\n".join(lines)


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
        choices=["json", "graphviz"],
        default="json",
        help="Output format (default: json)",
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

    if args.format == "json":
        print(graph.to_json())
    else:
        print(graph.to_graphviz())


if __name__ == "__main__":
    main()
