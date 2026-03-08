import unittest

from nixoscope import ModuleGraphEdge

_KNOWN_MODULE_SOURCE: str = "xxxxx"
_KNOWN_MODULE_PATH: str = "nix/store/foo/bar/module.nix"
_MODULE_OPTION: str = "foo.bar.baz.qux"
_MODULE_LAMDBA_OPTION: str = 'foo.bar.__functor.<function body>.<function body>.__functor.<function body>.<function body>.includes."[definition 1-entry 2]".<function body>.includes."[definition 1-entry 1]".<function body>.baz'
_MODULE_LAMDBA_OPTION_CHAIN: str = "foo.bar.<unknown-function-chain>"

_KNOWN_MODULE = {
    "disabled": False,
    "file": f"{_KNOWN_MODULE_SOURCE}-source/{_KNOWN_MODULE_PATH}",
    "imports": [],
    "key": "",
}

_KNOWN_MODULE_WITH_OPTION = {
    "disabled": False,
    "file": f"{_KNOWN_MODULE_SOURCE}-source/{_KNOWN_MODULE_PATH}, via option {_MODULE_OPTION}",
    "imports": [],
    "key": "",
}

_KNOWN_MODULE_WITH_LAMBDA_OPTION = {
    "disabled": False,
    "file": f"{_KNOWN_MODULE_SOURCE}-source/{_KNOWN_MODULE_PATH}, via option {_MODULE_LAMDBA_OPTION}",
    "imports": [],
    "key": "",
}

_UNKNOWN_MODULE_SOURCE: str = "<unknown-source>"
_UNKNOWN_MODULE_PATH: str = "<unknown-module>"
_UNKNOWN_MODULE_KEY: str = "anon-1:anon-2"

_UNKNOWN_MODULE = {
    "disabled": False,
    "file": "<unknown-file>",
    "imports": [],
    "key": _UNKNOWN_MODULE_KEY,
}
_UNKNOWN_MODULE_WITH_OPTION = {
    "disabled": False,
    "file": f"<unknown-file>, via option {_MODULE_OPTION}",
    "imports": [],
    "key": _UNKNOWN_MODULE_KEY,
}
_UNKNOWN_MODULE_WITH_LAMBD_OPTION = {
    "disabled": False,
    "file": f"<unknown-file>, via option {_MODULE_LAMDBA_OPTION}",
    "imports": [],
    "key": _UNKNOWN_MODULE_KEY,
}


class TestModuleGraphEdge(unittest.TestCase):
    def test_parsing_known_module(self) -> None:
        edge = ModuleGraphEdge(_KNOWN_MODULE)
        self.assertEqual(edge.source, _KNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _KNOWN_MODULE_PATH)
        self.assertEqual(edge.key, "")
        self.assertEqual(edge.option, "")

    def test_parsing_known_module_with_option(self) -> None:
        edge = ModuleGraphEdge(_KNOWN_MODULE_WITH_OPTION)
        self.assertEqual(edge.source, _KNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _KNOWN_MODULE_PATH)
        self.assertEqual(edge.key, "")
        self.assertEqual(edge.option, _MODULE_OPTION)

    def test_parsing_known_module_with_lambda_option(self) -> None:
        edge = ModuleGraphEdge(_KNOWN_MODULE_WITH_LAMBDA_OPTION)
        self.assertEqual(edge.source, _KNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _KNOWN_MODULE_PATH)
        self.assertEqual(edge.key, "")
        self.assertEqual(edge.option, _MODULE_LAMDBA_OPTION_CHAIN)

    def test_parsing_unknown_module(self) -> None:
        edge = ModuleGraphEdge(_UNKNOWN_MODULE)
        self.assertEqual(edge.source, _UNKNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _UNKNOWN_MODULE_PATH)
        self.assertEqual(edge.key, str(abs(hash(_UNKNOWN_MODULE_KEY))))
        self.assertEqual(edge.option, "")

    def test_parsing_unknown_module_with_option(self) -> None:
        edge = ModuleGraphEdge(_UNKNOWN_MODULE_WITH_OPTION)
        self.assertEqual(edge.source, _UNKNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _UNKNOWN_MODULE_PATH)
        self.assertEqual(edge.key, str(abs(hash(_UNKNOWN_MODULE_KEY))))
        self.assertEqual(edge.option, _MODULE_OPTION)

    def test_parsing_unknown_module_with_lambda_option(self) -> None:
        edge = ModuleGraphEdge(_UNKNOWN_MODULE_WITH_LAMBD_OPTION)
        self.assertEqual(edge.source, _UNKNOWN_MODULE_SOURCE)
        self.assertEqual(edge.module, _UNKNOWN_MODULE_PATH)
        self.assertEqual(edge.key, str(abs(hash(_UNKNOWN_MODULE_KEY))))
        self.assertEqual(edge.option, _MODULE_LAMDBA_OPTION_CHAIN)

    def test_to_dict_without_option(self) -> None:
        edge = ModuleGraphEdge(_KNOWN_MODULE)
        self.assertEqual(edge.to_dict(), {"source": _KNOWN_MODULE_SOURCE, "module": _KNOWN_MODULE_PATH, "key": ""})

    def test_to_dict_with_option(self) -> None:
        edge = ModuleGraphEdge(_KNOWN_MODULE_WITH_OPTION)
        self.assertEqual(
            edge.to_dict(),
            {"source": _KNOWN_MODULE_SOURCE, "module": _KNOWN_MODULE_PATH, "key": "", "option": _MODULE_OPTION},
        )


if __name__ == "__main__":
    unittest.main()
