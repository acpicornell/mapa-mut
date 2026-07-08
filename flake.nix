{
  description = "mapa-mut — toponym extraction & georeferencing for the 1683 Mallorca map by Vicenç Mut";

  # nixpkgs is pinned (see flake.lock) for a byte-identical toolchain. The revision
  # matches the sibling ../mapkurator-mps flake so both projects share one nixpkgs.
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/f205b5574fd0cb7da5b702a2da51507b7f4fdd1b";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in
    {
      # One reproducible shell for the whole toponym pipeline. Python carries the
      # geometry/fuzzy/georeference work; Node runs the review server and ngib-fetch.
      # Text detection itself is delegated to the sibling ../mapkurator-mps flake
      # (Apple MPS spotter); see scripts/toponims/mapkurator/README.md.
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: with ps; [
              rapidfuzz     # fast fuzzy string matching for NGIB name scoring
              jellyfish     # phonetic similarity (metaphone, jaro-winkler) for old spellings
              scipy         # thin-plate-spline georeference + cKDTree nearest neighbour
              numpy
              scikit-learn
              unidecode     # accent folding for cleanup/matching
              shapely       # real polygon geometry + IoU for deduping detections
              pillow        # tiling, crop rendering, review previews
            ]))
            pkgs.nodejs
          ];
        };
      });
    };
}
