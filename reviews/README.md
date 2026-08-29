# Semantic review baselines

Each `<package-id>.json` file records exact SHA-256 values for Lua files whose
elevated behavior or Semgrep parser gaps were manually reviewed by catalog
maintainers. These baselines are trusted only from the catalog's base branch;
a package submission cannot approve itself by adding or changing one in its PR.

When semantic admission fails, download the `semantic-review-*` artifact,
review the candidate's listed files and findings, and add the candidate as
`reviews/<package-id>.json` in a separate maintainer-reviewed change. Critical
findings cannot be approved. Any subsequent byte change invalidates that file's
approval automatically.
