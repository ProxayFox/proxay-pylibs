{
  description = "A Nix-flake-based Python development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      python = pkgs.python313;
      venvDir = ".venv";
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          (python.withPackages (
            ps: with ps; [
              uv

              # Coding Stuff
              python-lsp-server
              black
              pylint
              ruff
              jedi
              mypy
            ]
          ))

          nix-ld
          yaml-language-server
          markdown-oxide

          # Utilities
          perf
          duckdb
        ];

        inputsFrom = with pkgs; [
          bat
        ];

        shellHook = ''
          export LD_LIBRARY_PATH=$NIX_LD_LIBRARY_PATH;
          uv sync
        '';
      };
    };
}
