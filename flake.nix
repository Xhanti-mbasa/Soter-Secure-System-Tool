{
  description = "Soter: Secure workspace tool for bug bounty hunters";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages.chromium-pentesting = pkgs.callPackage ./packages/chromium-pentesting.nix {};
        apps.chromium-pentesting = {
          type = "app";
          program = "${self.packages.${system}.chromium-pentesting}/bin/chromium-pentesting";
        };
      }
    );
}
