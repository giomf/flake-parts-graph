"""visualizer - Strategy implementations for rendering a ModuleGraph.

Each concrete :class:`Visualizer` encapsulates one output format.  Pass an
instance to :meth:`~module_graph.ModuleGraph.render` to produce output.

Available strategies:

* :class:`GraphvizVisualizer` - Graphviz DOT / ``.gv``
* :class:`JsonVisualizer`     - structured JSON
* :class:`MermaidVisualizer`  - Mermaid ``flowchart TD``
"""

from __future__ import annotations

import colorsys
import html
import json
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import graphviz
import graphviz.encoding

from nixoscope.module_graph import UNKNOWN_SOURCE

if TYPE_CHECKING:
    from nixoscope.module_graph import ModuleGraph

_SAFE_MERMAID_ID_RE: re.Pattern[str] = re.compile(r"[^a-zA-Z0-9]")


class Visualizer(ABC):
    """Abstract base class for all ModuleGraph output strategies.

    Subclasses implement :meth:`render` to produce a string representation
    of the graph in a specific format.  The shared :meth:`_color_from_source`
    helper derives a stable pastel colour from a Nix store hash so that nodes
    belonging to the same derivation are visually grouped across formats.
    """

    @abstractmethod
    def render(self, graph: ModuleGraph) -> str:
        """Render *graph* and return the result as a string.

        Args:
            graph: The :class:`~module_graph.ModuleGraph` to render.

        Returns:
            A string representation of the graph in the concrete format.

        """

    @staticmethod
    def _color_from_source(source: str) -> str:
        """Derive a stable pastel hex colour from *source*.

        Uses a golden-angle hue step (137°) so that hashes that are
        numerically close still produce visually distinct colours.

        Args:
            source: A Nix store hash string used as the colour seed.

        Returns:
            A CSS hex colour string such as ``#a3c4f5``.

        """
        n = abs(hash(source))
        hue = (n * 137) % 360
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.80, 0.5)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class JsonVisualizer(Visualizer):
    """Render the graph as structured JSON.

    Each node is serialised via :meth:`~module_graph.ModuleGraphNode.to_dict`,
    producing a list of objects with ``source``, ``module``, ``key``, and
    optionally ``option`` and ``imports`` fields.
    """

    def render(self, graph: ModuleGraph) -> str:
        """Return a pretty-printed JSON string of all graph nodes."""
        result = [node.to_dict() for node in graph.modules.values()]
        return json.dumps(result, indent=2)


class GraphvizVisualizer(Visualizer):
    """Render the graph as a Graphviz DOT digraph.

    Node labels show the module filename in bold, the triggering option on a
    second line, and the source hash in italics.  Nodes from the same
    derivation share a pastel background colour.
    """

    def render(self, graph: ModuleGraph) -> str:
        """Return the Graphviz DOT source string for *graph*."""
        dot = graphviz.Digraph("ModuleGraph")
        dot.attr("node", shape="box", fontname="Helvetica", style="filled")

        for (source, module, key), node in graph.modules.items():
            node_id = graphviz.escape(f"{source}-{module}")
            if source == UNKNOWN_SOURCE:
                node_id = graphviz.escape(f"{node_id}-{key}")
            label = f"<<B>{html.escape(module)}</B><BR/>{html.escape(node.option)}<BR/><I>{html.escape(source)}</I>>"
            dot.node(name=node_id, label=label, fillcolor=self._color_from_source(source))

        for (source, module, key), node in graph.modules.items():
            from_id = graphviz.escape(f"{source}-{module}")
            if source == UNKNOWN_SOURCE:
                from_id = graphviz.escape(f"{from_id}-{key}")
            for edge in node.imports:
                to_id = graphviz.escape(f"{edge.source}-{edge.module}")
                if edge.source == UNKNOWN_SOURCE:
                    to_id = graphviz.escape(f"{to_id}-{edge.key}")
                dot.edge(from_id, to_id)

        return str(dot)


class MermaidVisualizer(Visualizer):
    """Render the graph as a Mermaid ``flowchart TD`` diagram.

    Node labels use Mermaid's Markdown string syntax (backtick-quoted) to
    render the module filename in bold and the source hash in italics, with
    the triggering option on a middle line when present.  Nodes from the same
    derivation share a pastel background colour applied via ``style``
    directives.
    """

    @staticmethod
    def _node_id(source: str, module: str, key: str) -> str:
        """Return a Mermaid-safe node identifier.

        Mermaid node IDs may only contain alphanumerics; all other characters
        are replaced with underscores and a leading ``n`` is prepended to
        avoid IDs that start with a digit.

        Args:
            source: Nix store hash of the owning derivation.
            module: Module file path relative to the store path.
            key:    Disambiguation key for unknown-source entries.

        """
        raw = f"{source}_{module}_{key}" if key else f"{source}_{module}"
        return "n" + _SAFE_MERMAID_ID_RE.sub("_", raw)

    def render(self, graph: ModuleGraph) -> str:
        """Return the Mermaid ``flowchart TD`` source string for *graph*."""
        lines = ["flowchart TD"]

        for (source, module, key), node in graph.modules.items():
            nid = self._node_id(source, module, key)
            parts = [f"**{module}**", node.option, f"_{source}_"]
            lines.append('    {}["`{}`"]'.format(nid, "\n".join(parts)))

        for (source, module, key), node in graph.modules.items():
            from_id = self._node_id(source, module, key)
            for edge in node.imports:
                to_id = self._node_id(edge.source, edge.module, edge.key)
                lines.append(f"    {from_id} --> {to_id}")

        for source, module, key in graph.modules:
            nid = self._node_id(source, module, key)
            lines.append(f"    style {nid} fill:{self._color_from_source(source)},color:#000000")

        return "\n".join(lines)
