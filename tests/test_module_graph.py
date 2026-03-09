import unittest

from nixoscope import ModuleGraph

_SOURCE: str = "abc123"
_STORE_PATH: str = f"/nix/store/{_SOURCE}-source"

_SIMPLE_GRAPH = {
    "disabled": False,
    "file": f"{_STORE_PATH}/flake.nix",
    "key": "",
    "imports": [
        {"disabled": False, "file": f"{_STORE_PATH}/foo.nix", "key": "", "imports": []},
        {"disabled": False, "file": f"{_STORE_PATH}/bar.nix", "key": "", "imports": []},
        {"disabled": False, "file": f"{_STORE_PATH}/baz.nix", "key": "", "imports": []},
    ],
}

_NESTED_GRAPH = {
    "disabled": False,
    "file": f"{_STORE_PATH}/flake.nix",
    "key": "",
    "imports": [
        {
            "disabled": False,
            "file": f"{_STORE_PATH}/level1.nix",
            "key": "",
            "imports": [
                {
                    "disabled": False,
                    "file": f"{_STORE_PATH}/level2.nix",
                    "key": "",
                    "imports": [
                        {
                            "disabled": False,
                            "file": f"{_STORE_PATH}/level3.nix",
                            "key": "",
                            "imports": [],
                        },
                    ],
                },
            ],
        },
    ],
}

_OPTION_GRAPH = {
    "disabled": False,
    "file": f"{_STORE_PATH}/flake.nix",
    "key": "",
    "imports": [
        {
            "disabled": False,
            "file": f"{_STORE_PATH}/services.nix, via option services",
            "key": "",
            "imports": [
                {
                    "disabled": False,
                    "file": f"{_STORE_PATH}/nginx.nix, via option services.nginx",
                    "key": "",
                    "imports": [],
                },
            ],
        },
        {
            "disabled": False,
            "file": f"{_STORE_PATH}/networking.nix, via option networking",
            "key": "",
            "imports": [],
        },
    ],
}


class TestSimpleGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = ModuleGraph([_SIMPLE_GRAPH], option_filter=None)

    def test_graph_has_four_nodes(self) -> None:
        self.assertEqual(len(self.graph.modules), 4)

    def test_graph_contains_flake_nix(self) -> None:
        self.assertIn((_SOURCE, "flake.nix", ""), self.graph.modules)

    def test_graph_contains_leaves(self) -> None:
        for leaf in ("foo.nix", "bar.nix", "baz.nix"):
            self.assertIn((_SOURCE, leaf, ""), self.graph.modules)

    def test_flake_nix_imports_all_leaves(self) -> None:
        flake_node = self.graph.modules[(_SOURCE, "flake.nix", "")]
        imported_modules = {edge.module for edge in flake_node.imports}
        self.assertEqual(imported_modules, {"foo.nix", "bar.nix", "baz.nix"})

    def test_leaves_have_no_imports(self) -> None:
        for leaf in ("foo.nix", "bar.nix", "baz.nix"):
            node = self.graph.modules[(_SOURCE, leaf, "")]
            self.assertEqual(node.imports, [])


class TestNestedGraph(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = ModuleGraph([_NESTED_GRAPH], option_filter=None)

    def test_graph_has_four_nodes(self) -> None:
        self.assertEqual(len(self.graph.modules), 4)

    def test_all_nodes_present(self) -> None:
        for module in ("flake.nix", "level1.nix", "level2.nix", "level3.nix"):
            self.assertIn((_SOURCE, module, ""), self.graph.modules)

    def test_flake_imports_level1(self) -> None:
        flake_node = self.graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertEqual(imported, {"level1.nix"})

    def test_level1_imports_level2(self) -> None:
        node = self.graph.modules[(_SOURCE, "level1.nix", "")]
        imported = {edge.module for edge in node.imports}
        self.assertEqual(imported, {"level2.nix"})

    def test_level2_imports_level3(self) -> None:
        node = self.graph.modules[(_SOURCE, "level2.nix", "")]
        imported = {edge.module for edge in node.imports}
        self.assertEqual(imported, {"level3.nix"})

    def test_level3_has_no_imports(self) -> None:
        node = self.graph.modules[(_SOURCE, "level3.nix", "")]
        self.assertEqual(node.imports, [])


class TestOptionFilter(unittest.TestCase):
    def test_no_filter_includes_all_nodes(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter=None)
        self.assertEqual(len(graph.modules), 4)
        for module in ("flake.nix", "services.nix", "nginx.nix", "networking.nix"):
            self.assertIn((_SOURCE, module, ""), graph.modules)

    def test_filter_includes_matching_excludes_non_matching(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="services")
        for module in ("flake.nix", "services.nix", "nginx.nix"):
            self.assertIn((_SOURCE, module, ""), graph.modules)
        self.assertNotIn((_SOURCE, "networking.nix", ""), graph.modules)

    def test_filter_excludes_unrelated_option_tree(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="networking")
        self.assertIn((_SOURCE, "flake.nix", ""), graph.modules)
        self.assertIn((_SOURCE, "networking.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "nginx.nix", ""), graph.modules)

    def test_filter_no_match_only_root_node_remains(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="nonexistent")
        self.assertEqual(len(graph.modules), 1)
        self.assertIn((_SOURCE, "flake.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "nginx.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "networking.nix", ""), graph.modules)

    def test_filter_matched_nodes_linked_to_root(self) -> None:
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="networking")
        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertIn("networking.nix", imported)
        self.assertNotIn("services.nix", imported)

    def test_nested_filter_reparents_children_to_root(self) -> None:
        # When a parent is filtered out, its matching children should link directly to root
        graph = ModuleGraph([_OPTION_GRAPH], option_filter="services.nginx")
        self.assertIn((_SOURCE, "nginx.nix", ""), graph.modules)
        self.assertNotIn((_SOURCE, "services.nix", ""), graph.modules)
        flake_node = graph.modules[(_SOURCE, "flake.nix", "")]
        imported = {edge.module for edge in flake_node.imports}
        self.assertIn("nginx.nix", imported)
        self.assertNotIn("services.nix", imported)


if __name__ == "__main__":
    unittest.main()
