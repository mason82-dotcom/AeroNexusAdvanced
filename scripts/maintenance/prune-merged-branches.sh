#!/usr/bin/env bash
# Safe, read-only by default. Use --apply only after reviewing candidate branches.
set -euo pipefail
REPO='mason82-dotcom/AeroNexusAdvanced'
MODE="${1:---dry-run}"
case "$MODE" in
  --dry-run|--apply) ;;
  *) echo "Usage: $0 [--dry-run|--apply]" >&2; exit 2 ;;
esac

command -v gh >/dev/null || { echo 'Install GitHub CLI (gh).' >&2; exit 1; }
gh auth status -h github.com >/dev/null 2>&1 || { echo 'Run gh auth login.' >&2; exit 1; }

default_branch="$(gh api "repos/$REPO" --jq '.default_branch')"
[[ -n "$default_branch" ]] || { echo 'Default branch unavailable.' >&2; exit 1; }
# Fetch first. GitHub failures must abort rather than yield partial inventories.
branches="$(gh api --paginate "repos/$REPO/branches?per_page=100" --jq '.[] | select(.protected == false) | .name')"
open_pr_heads="$(gh api --paginate "repos/$REPO/pulls?state=open&per_page=100" \
  --jq ".[] | select(.head.repo.full_name == \"$REPO\") | .head.ref")"
candidates=()
printf 'Repository: %s | default branch: %s\n' "$REPO" "$default_branch"
while IFS= read -r branch; do
  [[ -n "$branch" && "$branch" != "$default_branch" ]] || continue
  case "$branch" in
    feat/*|feature/*|fix/*|test/*|integration/*) ;;
    *) printf 'KEEP (other branch): %s\n' "$branch"; continue ;;
  esac
  if grep -Fxq -- "$branch" <<< "$open_pr_heads"; then
    printf 'KEEP (open PR): %s\n' "$branch"
    continue
  fi
  ahead="$(gh api "repos/$REPO/compare/$default_branch...$branch" --jq '.ahead_by')"
  [[ "$ahead" =~ ^[0-9]+$ ]] || { echo "Invalid ahead count for $branch" >&2; exit 1; }
  if (( ahead == 0 )); then
    printf 'CANDIDATE: %s\n' "$branch"
    candidates+=("$branch")
  else
    printf 'KEEP (%s unique commits): %s\n' "$ahead" "$branch"
  fi
done <<< "$branches"

printf 'Eligible: %d\n' "${#candidates[@]}"
if [[ "$MODE" == '--dry-run' || ${#candidates[@]} -eq 0 ]]; then
  echo 'No changes made.'
  exit 0
fi
[[ -t 0 ]] || { echo 'Interactive terminal required.' >&2; exit 1; }
read -r -p "Type DELETE $REPO to remove eligible remote branches: " confirmation
[[ "$confirmation" == "DELETE $REPO" ]] || { echo 'Aborted.'; exit 1; }
for branch in "${candidates[@]}"; do
  # Recheck for new commits before each remote deletion.
  ahead="$(gh api "repos/$REPO/compare/$default_branch...$branch" --jq '.ahead_by')"
  if [[ "$ahead" != 0 ]]; then
    printf 'SKIP (branch changed): %s\n' "$branch"
    continue
  fi
  gh api -X DELETE "repos/$REPO/git/refs/heads/$branch" >/dev/null
  printf 'DELETED: %s\n' "$branch"
done
