#!/usr/bin/env python
import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModuleNode:
    imports: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class ModuleGraph:
    modules: dict[str, ModuleNode] = field(default_factory=dict)

    def get_node(self, name: str) -> ModuleNode:
        if name not in self.modules:
            self.modules[name] = ModuleNode()
        return self.modules[name]

    def add_file(self, module_name: str, filename: str) -> None:
        node = self.get_node(module_name)
        if filename not in node.files:
            node.files.append(filename)

    def add_import(self, from_module: str, to_module: str) -> None:
        node = self.get_node(from_module)
        if to_module not in node.imports:
            node.imports.append(to_module)

    def to_json(self) -> str:
        return json.dumps(
            {name: {"imports": node.imports, "files": node.files} for name, node in self.modules.items()}, indent=2
        )

    def to_graphviz(self) -> str:
        lines = ["digraph ModuleGraph {", '\tnode [shape=box fontname="Helvetica"]']
        for module_name, node in self.modules.items():
            escaped_name = module_name.replace('"', '\\"')
            label_parts = [f"<b>{module_name}</b>"]
            if node.files:
                label_parts.append("<br/><br/>")
                italic_files = [f"<i>{f}</i>" for f in node.files]
                label_parts.append("<br/>".join(italic_files))
            label = "".join(label_parts)
            lines.append(f'\t"{escaped_name}" [label=<{label}>];')
        for module_name, node in self.modules.items():
            escaped_from = module_name.replace('"', '\\"')
            for imported_module in node.imports:
                escaped_to = imported_module.replace('"', '\\"')
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
        "--graphviz",
        action="store_true",
        help="Output in Graphviz DOT format instead of JSON",
    )
    return parser.parse_args()


def load_json(json_file: Path) -> dict:
    """Load and return data from a JSON file."""
    f = json_file.open()
    return json.load(f)


def parse_file(file: str) -> dict | None:
    """Extract module name from file path.

    Only processes files with ", via option " in the path.
    Returns None for files without this pattern.
    """
    if ", via option " not in file:
        return None

    parts = file.split(", via option ", 1)
    file_name = parts[0].split("/", 4)[-1]
    module_name = parts[1].removeprefix("flake.modules.")
    return {"file_name": file_name, "module_name": module_name}


def process_entry(entry: dict, graph: ModuleGraph, parent_module: str | None = None) -> None:
    """Process a single entry from the graph JSON and add it to the ModuleGraph."""
    file_path = entry.get("file", "")
    if not file_path:
        return

    names = parse_file(file_path)

    current_module = None
    if names is not None:
        file_name = names["file_name"]
        module_name = names["module_name"]
        current_module = module_name

        # Add the file to the module
        graph.add_file(module_name, file_name)

        # Add import from parent module if exists and different
        if parent_module is not None and parent_module != module_name:
            graph.add_import(parent_module, module_name)

    # Process imports recursively
    # Pass current_module if we found one, otherwise pass parent_module to maintain chain
    imports = entry.get("imports", [])
    for imported_entry in imports:
        process_entry(imported_entry, graph, current_module or parent_module)


def build_graph(data: list) -> ModuleGraph:
    """Build a ModuleGraph from the loaded JSON data."""
    graph = ModuleGraph()

    for entry in data:
        process_entry(entry, graph)

    return graph


if __name__ == "__main__":
    args = parse_args()
    data = load_json(args.input)

    graph = build_graph(data)  # ty:ignore[invalid-argument-type]
    if args.graphviz:
        print(graph.to_graphviz())
    else:
        print(graph.to_json())
