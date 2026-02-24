#!/usr/bin/env python
import json
import sys
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

    def __str__(self) -> str:
        return json.dumps(
            {name: {"imports": node.imports, "files": node.files} for name, node in self.modules.items()}, indent=2
        )


def load_json_file(json_file: Path) -> dict:
    """Load and return data from a JSON file."""
    f = json_file.open()
    return json.load(f)


def parse_via_option(file_str: str) -> dict | None:
    if ", via option " not in file_str:
        return None
    path_part, module_part = file_str.split(", via option ", 1)
    return {
        "filename": path_part.strip().rsplit("/", 1)[-1],
        "module_name": module_part.strip(),
    }


def build_graph(
    node: dict,
    graph: ModuleGraph | None = None,
    parent_module_name: str | None = None,
) -> ModuleGraph:
    if graph is None:
        graph = ModuleGraph()

    file_str = node.get("file", "")
    element = parse_via_option(file_str)
    current_module_name = element["module_name"] if element else parent_module_name

    if current_module_name is not None:
        graph.get_node(current_module_name)

        if element:
            graph.add_file(current_module_name, element["filename"])

        if element and parent_module_name and parent_module_name != current_module_name:
            graph.add_import(parent_module_name, current_module_name)

    for child in node.get("imports", []):
        build_graph(child, graph, current_module_name)

    return graph


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "graph.json"
    data = load_json_file(Path(filepath))
    root = next((el for el in data if el.get("file", "").endswith("/flake.nix")), None)
    if not root:
        print("No element found with a file ending in '/flake.nix'.")
        sys.exit(1)

    graph = build_graph(root)
    print(graph)
