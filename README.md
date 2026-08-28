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
7. Set the Actions variable `VANAHUB_SCREENSHOT_UPLOAD_URL` to the upload
   Worker origin and set the Actions secret `VANAHUB_MEDIA_CLEANUP_SECRET` to
   the same random value as the Worker's `CLEANUP_SECRET`. Cleanup is
   best-effort; also configure the R2 bucket to expire `pending/` objects after
   30 days as the recovery path for interrupted runs.
8. Create a protected `profile-publishing` environment and restrict approvals
   to catalog maintainers. Final release publication passes through this
   environment after the exact manifest PR is merged and the resulting catalog
   is validated and signed.

An administrator can verify these repository controls before the first profile
publication:

```sh
python3 scripts/profile_repository_preflight.py Hildaware/vanahub-catalog
```

Routine maintainer PRs may change exactly one `packages/<id>/manifest.json`.
Trusted initial-admission automation also records the originating issue in
`packages/<id>/provenance.json`, and trusted catalog automation may add up to
eleven normalized, content-addressed JPEGs beneath `media/<id>/`. Admission
validates package provenance, verifies every media
filename against its fully decoded bytes and requires `iconUrl` or `screenshots`
to reference it.
Workflow, policy, schema, revocation, and signing changes require catalog
administrator review.

## Publisher automation

First admission begins with the **Submit an addon to VanaHub** issue form. The
issue author must be authorized in the public source repository's
`.vanahub.json`. Catalog Actions discover the newest stable GitHub Release,
re-scan its normalized artifact, copy Publisher-staged R2 uploads into immutable
catalog media, and open the admission PR. The issue receives a preview of
normalized bytes pinned to the automation commit. GitHub Pages, rather
than the author ZIP or temporary upload bucket, is the permanent media host.
New external image URLs are not accepted; already-normalized media from existing
packages is preserved until an author replaces it through Publisher.

After admission, `discover.yml` checks registered repositories every 30
minutes. A newer stable release is eligible only when it contains
`vanahub-manifest.json` and the exact normalized artifact named by that
manifest. Drafts and prereleases are ignored. Discovered updates still pass
through the same admission and auto-merge checks as maintainer-authored PRs.
Each distinct scan result is posted once to the originating submission issue.
A rejected release reopens that issue for maintainer attention, even when the
issue was previously closed.

`packages/example/manifest.example.json` is documentation only. Copy it to a
new `packages/<real-id>/manifest.json` and replace every placeholder when
submitting the first real package.

## Maintainer profile publication

Catalog profiles are versioned settings archives; they never contain addon
binaries. The recommended maintainer path validates the local export and live
repository controls, creates the correctly named draft asset, and starts
preparation:

```sh
python3 scripts/submit_profile.py ./my-profile.vanahub-profile.zip \
  --id starter-profile --version 1.0.0 \
  --description "Portable starter settings." --author "VanaHub" \
  --categories quality-of-life --confirm-public
```

For manual recovery, create a draft GitHub Release tagged
`profile-<id>-v<semver>`, attach the export as
`<id>-<semver>.source.vanahub-profile.zip`, and run **Prepare catalog
profile**. Use `--replace-source` with the helper only when intentionally
retrying that same draft version.

Preparation applies the same archive and settings-content restrictions as the
client importer. It redacts supported structured credential values, blocks
ambiguous or unsafe content, reports possible personal data without printing
the matched values, and produces a public-safe report before the source asset
is replaced by a deterministic `<id>-<semver>.vanahub-profile.zip`. The
generated manifest PR is independently revalidated and must receive its normal
protected-branch approval. The release remains private until that exact PR is
merged, the merged catalog is validated, and its next index is signed. Profile
versions must increase according to SemVer. If finalization is interrupted,
rerun **Publish signed catalog** with the admitted draft release tag.

Do not publish the first profile until the catalog-profile download client is
released. Older clients can browse the expanded metadata but cannot restore
the hosted settings archive.
