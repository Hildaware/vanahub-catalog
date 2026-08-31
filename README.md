# VanaHub Catalog

The VanaHub Catalog is the public directory of addons available through
[VanaHub](https://github.com/Hildaware/vanahub), an addon browser and manager
for Ashita v4.

This repository is the contact point for addon developers who want their work
listed in VanaHub. It will also become the home of shared VanaHub profiles.

## How VanaHub works

VanaHub connects three parts of the publishing flow:

1. **Addon developers publish on GitHub.** You keep ownership of your source,
   releases, and release notes.
2. **VanaHub Publisher prepares each release.** It checks the addon, creates a
   consistent installable package, and adds the information the catalog needs.
3. **The catalog reviews and lists the release.** VanaHub clients receive the
   signed catalog and can install or update the addon from its original GitHub
   Release.

You submit an addon only once. After it is accepted, new stable releases are
discovered automatically.

## List your addon

Before starting, make sure that:

- the addon is for Ashita v4;
- its source is in a public GitHub repository;
- you have permission to publish the addon;
- the addon has a clear entrypoint and can be packaged from one directory; and
- releases use semantic versions such as `v1.2.0`.

Then complete the one-time setup:

1. Open [VanaHub Publisher](https://hildaware.github.io/vanahub-publisher/).
2. Paste the public GitHub repository URL and select the addon directory.
3. Add the name, description, author, maintainers, categories, and optional
   screenshots. Publisher will guide you through validation.
4. Save the generated workflow as
   `.github/workflows/vanahub-setup.yml` in your repository, commit it to the
   default branch, and run **VanaHub publishing** once from the GitHub Actions
   tab with the release-tag field left blank.
5. Review and merge the setup pull request created in your repository.
6. Publish a stable GitHub Release. The release tag becomes the addon version,
   and the release notes become its changelog in VanaHub.
7. When **VanaHub publishing** finishes, open that workflow run in the GitHub
   Actions tab and follow its **submit this release to VanaHub** link. The link
   opens a submission already filled in for your validated release.

Publisher creates and maintains the files needed by VanaHub, so you do not
need to hand-write a catalog manifest or package ZIP. If your repository
already creates releases with GitHub Actions, Publisher will show the small
integration step needed to connect that workflow.

The first release is reviewed before it appears in the catalog. The submission
issue will show progress and any changes that are needed. If you no longer have
the generated link, you can use the [addon submission form](https://github.com/Hildaware/vanahub-catalog/issues/new?template=vanahub-submission.yml)
and enter the repository URL and package ID manually.

## Publish an update

After the first version is accepted, your normal release process is the update
process:

1. Update the addon in its GitHub repository.
2. Publish a new stable GitHub Release with a higher semantic version.
3. Let the installed VanaHub publishing workflow prepare the release.

The catalog checks registered repositories regularly and submits eligible new
versions for review. Drafts and prereleases are not listed. If you need an
immediate check, use the [update request form](https://github.com/Hildaware/vanahub-catalog/issues/new?template=vanahub-update.yml).

## What catalog review means

Every candidate artifact is scanned structurally and then analyzed with pinned
Semgrep rules at initial submission, update discovery, admission, and final
publication. Elevated behavior and parser gaps require a maintainer-reviewed
exact-file baseline under `reviews/`; critical findings cannot be approved.
Changing a reviewed file invalidates its approval automatically.

Catalog addons must pass VanaHub's automated package and Lua checks.
These checks keep installs predictable and reject behavior that is outside the
built-in catalog's intentionally limited scope.

A catalog listing means that a specific release passed the published checks;
it is not a guarantee that software is bug-free or safe in every situation.
Users should still review an addon's source, maintainer, permissions, and
release notes before installing it.

## Profile sharing

VanaHub profiles let players share an addon list, load order, auto-load choices,
and selected settings without redistributing addon binaries. VanaHub shows the
contents before installation and obtains each addon from its catalog source.

Public profile sharing will use the same catalog review model, including checks
for unsupported files, credentials, and possible personal information. Profile
submissions are not generally open yet; public instructions will be added here
when the sharing flow is ready.

## Private distributor access

Community-distribution evidence is read from the private `Hildaware/vanahub-addon-distro` repository with short-lived tokens from the VanaHub distributor GitHub App. Install the App on both repositories with **Contents: read** and **Issues: read and write**, then set `VANAHUB_DISTRIBUTOR_APP_ID` and `VANAHUB_DISTRIBUTOR_APP_PRIVATE_KEY` as catalog repository secrets and `VANAHUB_DISTRIBUTOR_APP_LOGIN` as the App bot-login repository variable.

The distributor only admits existing public upstream GitHub Release ZIPs. It does not build, repackage, or host addon binaries.

## Questions and support

If Publisher validation fails, start with the explanation it provides. For a
catalog submission question or a result that seems incorrect, open an issue in
this repository and include the public addon repository and release tag. Do not
post tokens, credentials, private settings, or other sensitive data.

For Publisher-specific documentation, see the
[VanaHub Publisher repository](https://github.com/Hildaware/vanahub-publisher).

Trusted community-distribution handoffs use the human semantic baseline and versioned SHA-bound attestation from `vanahub-addon-distro`; the catalog independently downloads and re-scans the exact artifact. Scanner or policy drift is retained as audit evidence but does not revoke approval for the identical artifact SHA. Ordinary and legacy catalog submissions continue using catalog-owned semantic review baselines.
