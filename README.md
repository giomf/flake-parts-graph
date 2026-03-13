# NixoScope

## Why This Tool Exists

I recently switched to the [dendritic design pattern with flake parts](https://github.com/Doc-Steve/dendritic-design-with-flake-parts) and needed a way to understand my module structure:

- **Which modules get imported from other modules?**
- **Which modules get declared in what files?**

Manually tracing these relationships through code was tedious and error-prone, so I built this tool to visualize the module dependency graph.

## How It Works

This tool leverages the new `.graph` output introduced in the Nixpkgs module system.
Thanks to [this merged PR](https://github.com/NixOS/nixpkgs/pull/403839), we can now obtain a JSON representing the tree of modules that took part in the evaluation of a configuration.

For more details, see the [announcement on NixOS Discourse](https://discourse.nixos.org/t/nixpkgs-module-system-config-modules-graph/67722).

## Usage

> [!TIP]  
> You can also use `nix run github:giomf/nixoscope` instead of cloning this repository and executing `nixoscope.py`

### Obtaining the input graph:  
`nix eval --json '.#nixosConfigurations.<your-config>.graph' > graph.json`

### Read the input graph:
`nixoscope.py --input graph.json`  
default: graph.json

### Output format:
#### Graphviz: 
`nixoscope.py --format gv`  
default: gv
#### Mermaid: 
`nixoscope.py --format mm`  
default: gv
#### JSON  
`nixoscope.py --format json`  
default: gv

### Filter by option prefix
`nixoscope.py --option "flake.modules"`  

## Result
![Graphviz output](./docs/graph.svg)
### Filtered by "flake.modules"
![Graphviz output](./docs/graph-filtered.svg)

## Disclaimer
This project uses AI as an aid.
