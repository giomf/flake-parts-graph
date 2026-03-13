"""module_graph - Build and render NixOS module import graphs.

Parses raw module graph data (as produced by ``nixos-option`` or similar
tooling) into a graph of :class:`ModuleGraphEdge` nodes.  Use a
:class:`~visualizer.Visualizer` strategy with :meth:`ModuleGraph.render`
to produce output in the desired format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .visualizer import Visualizer

UNKNOWN_SOURCE: str = "<unknown-source>"
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
            self.source = UNKNOWN_SOURCE
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

    def to_dict(self) -> dict:
        """Serialise to a plain dict, omitting ``option`` when empty."""
        return {"source": self.source, "module": self.module, "key": self.key} | (
            {"option": self.option} if self.option else {}
        )

    def __eq__(self, other: object) -> bool:
        """Two edges are equal when they point to the same source/module pair.

        For unknown-source entries the ``key`` is also compared because the
        module name is always ``<unknown-module>`` and therefore not unique.
        """
        if not isinstance(other, ModuleGraphEdge):
            return NotImplemented
        eq = self.source == other.source and self.module == other.module
        if UNKNOWN_SOURCE in (self.source, other.source):
            return eq and self.key == other.key
        return eq

    def __hash__(self) -> int:
        """Hash based on the same fields used by ``__eq__``."""
        return hash((self.source, self.module, self.key))


@dataclass
class ModuleGraphNode(ModuleGraphEdge):
    """A node in the module graph, extending :class:`ModuleGraphEdge` with its outgoing imports.

    Attributes:
        imports: Ordered list of edges to modules directly imported by this node.

    """

    imports: list[ModuleGraphEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise node and all its imports recursively to a plain dict."""
        return super().to_dict() | {"imports": [module.to_dict() for module in self.imports]}

    def __eq__(self, other: object) -> bool:
        """Inherit equality semantics from :class:`ModuleGraphEdge`."""
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Inherit hash semantics from :class:`ModuleGraphEdge`."""
        return super().__hash__()


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

    def render(self, visualizer: Visualizer) -> str:
        """Render the graph using *visualizer* and return the result as a string."""
        return visualizer.render(self)
