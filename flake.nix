{
  description = "A simple flake-parts-graph (fpg) analyser that prints the import order of nixos modules";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";

  };
  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # Loads pyproject.toml into a high-level project representation
      # Do you notice how this is not tied to any `system` attribute or package sets?
      # That is because `project` refers to a pure data representation.
      project = pyproject-nix.lib.project.loadPyproject {
        # Read & unmarshal pyproject.toml relative to this project root.
        # projectRoot is also used to set `src` for renderers such as buildPythonPackage.
        projectRoot = ./.;
      };

      # Variable to easily change Python version
      pythonVersion = "313"; # 311 for Python 3.11, 312 for Python 3.12, etc.
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          pp = pkgs."python${pythonVersion}Packages";
        in
        {
          default = pkgs.mkShell {
            buildInputs = [
              pkgs.jq
              pkgs.ruff
              pkgs.ty
              pkgs.uv
              pp.python
              # Only used for goto definiton/...
              pp.python-lsp-server
            ];
          };
        }
      );
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          pp = pkgs."python${pythonVersion}Packages";
          # Returns an attribute set that can be passed to `buildPythonPackage`.
          attrs = project.renderers.buildPythonPackage { python = pp.python; };
        in
        {
          # Pass attributes to buildPythonPackage.
          default = pp.python.pkgs.buildPythonPackage (attrs);
        }
      );
    };
}
