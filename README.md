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

## Installation

### Clone and run directly
```bash
git clone https://github.com/giomf/nixoscope
cd nixoscope
python -m nixoscope.nixoscope --help
```

### Install from nixpkgs
```bash
nix-shell -p nixoscope
# or with flakes
nix profile install nixpkgs#nixoscope
```

### Run without installing
```bash
nix run github:giomf/nixoscope -- --help
```

## Usage

### Obtaining the input graph:  
```bash
nix eval --json '.#nixosConfigurations.<your-config>.graph' > graph.json
```

### Read the input graph:
```bash
nixoscope --input graph.json
```
default: graph.json

### Output format:
#### Graphviz: 
```bash
nixoscope --format gv
```
default: gv
#### Mermaid: 
```bash
nixoscope --format mm
```
default: gv
#### JSON  
```bash
nixoscope --format json
```
default: gv

### Filter by option prefix
```bash
nixoscope --option "flake.modules"
```

## Result
![Graphviz output](./docs/graph.svg)
### Filtered by "flake.modules"
![Graphviz output](./docs/graph-filtered.svg)

## Disclaimer
This project uses AI as an aid.
