# Repository maintenance – AeroNexusAdvanced

This guide concerns GitHub repository hygiene. It must not be used to
remove data from the running Raspberry Pi, DJI Cloud API server, MinIO
or saved drone missions.

## Inventory on 18 October 2026

- Default branch: main (d2e530f03d568b0580a285a5229fcadcee8ac4e1 at inspection).
- 29 branches were found. Of the 28 non-default branches, 25 had zero unique
  commits compared with main. They may be deleted after rechecking ancestry.
- Preserve feature/pilot2-direct-wayline-upload-cli-20261017: open
  [PR #44](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/44),
  8 commits ahead of main. The write-enabled DJI backend integration was
  not tested against production.
- Preserve test/survey-leaflet-regression-20261018: open
  [PR #62](https://github.com/mason82-dotcom/AeroNexusAdvanced/pull/62),
  one unique commit; review CI before merging.
- Preserve feat/cloudapi2-bridge-hardening-20261016: four unique commits
  at inspection and no open PR; inspect it separately.

These figures represent a dated snapshot. Deleting a remote branch that has
zero unique commits does not erase commits already contained in main, but
does not clean up any local clones or working directories.

## Safe remote branch cleanup

Use GitHub CLI (gh) with an authenticated account that has suitable
repository rights. The helper script reports candidates without deletion
unless --apply is supplied:

~~~bash
bash scripts/maintenance/prune-merged-branches.sh
# Only after carefully reviewing the candidates:
bash scripts/maintenance/prune-merged-branches.sh --apply
~~~

When applying, the script requires an interactive terminal and exact
confirmation by entering the repository name. It skips protected branches,
open same-repository PR heads and branches outside known temporary prefixes.
Each candidate must have zero unique commits against the current default
branch, including at the final comparison immediately before deletion.
An API error aborts the operation.

## Keep production data intact

The repository ignores private environment files, config/pki/, the local
cloud-server/ staging area, var/, locally generated SQLite state, build
artifacts, browser reports and test caches. The public .env.example remains
tracked. Ignore patterns do not remove any file already tracked in Git;
inspect tracked secrets separately.

**Never run git clean -fdx on the production Pi checkout.** This can erase
ignored private credentials, databases, object metadata, local runtime
state and virtual environments. Do not delete Docker volumes, MinIO media,
broker state, drone telemetry or saved flight missions as part of Git
housekeeping.

To inspect the Pi checkout without changing deployed files:

~~~bash
cd ~/Projekte/AeroNexusAdvanced
git status --short --branch
git remote -v
git fetch --prune --dry-run origin
systemctl --user is-active aeronexusadvanced
~~~

A real fetch/prune, branch switch, dependency installation, merge or
service restart should be reviewed separately. Existing docs/ checkpoint
files contain historical versions, old PR numbers and past test results;
they are not a source of current production state.

## Routine

- Keep main deployable. Review runtime changes via pull requests.
- Run CI before merging; distinguish mock tests from Pi/device validation.
- Remove integrated temporary remote branches after a fresh comparison.
- Preserve unmerged commits, open PRs and all private production data.
