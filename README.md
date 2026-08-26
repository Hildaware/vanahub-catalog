# VanaHub public catalog repository template

This directory is copied into a separate hardened repository. The product
source and public package-submission history intentionally do not share a Git
repository.

Before enabling workflows:

1. Replace `OWNER/PRODUCT_REPOSITORY` and `PINNED_PRODUCT_COMMIT` with the
   product repository and an immutable reviewed commit.
2. Configure branch protection and allow auto-merge only after `admission`.
3. Add `VANAHUB_ED25519_PRIVATE_KEY` to the protected `github-pages`
   environment as a base64-encoded 32-byte Ed25519 seed. Publication fails if
   the key or detached signature is missing.
4. Replace the placeholder public key in the product and publish a client
   release before signing production indexes.
5. Enable GitHub Pages deployment from Actions.
6. Optionally enable **Allow GitHub Actions to create and approve pull
   requests** for zero-click submission PRs. Otherwise, successful submission
   runs provide a link for opening the validated branch as a PR. The workflow
   creates its tracking label automatically.

Routine maintainer PRs may change exactly one `packages/<id>/manifest.json`.
Trusted catalog automation may additionally add up to ten normalized,
content-addressed JPEGs beneath `media/<id>/`. Admission verifies every media
filename against its bytes and requires the package manifest to reference it.
Workflow, policy, schema, revocation, and signing changes require catalog
administrator review.

## Publisher automation

First admission begins with the **Submit an addon to VanaHub** issue form. The
issue author must be authorized in the public source repository's
`.vanahub.json`. Catalog Actions discover the newest stable GitHub Release,
re-scan its normalized artifact, copy screenshot URLs or Publisher-staged R2
uploads into immutable catalog media, and open the admission PR. The issue
receives a screenshot preview before the PR is created. GitHub Pages, rather
than the author ZIP or temporary upload bucket, is the permanent media host.

After admission, `discover.yml` checks registered repositories every 30
minutes. A newer stable release is eligible only when it contains
`vanahub-manifest.json` and the exact normalized artifact named by that
manifest. Drafts and prereleases are ignored. Discovered updates still pass
through the same admission and auto-merge checks as maintainer-authored PRs.

`packages/example/manifest.example.json` is documentation only. Copy it to a
new `packages/<real-id>/manifest.json` and replace every placeholder when
submitting the first real package.
