#!/usr/bin/env bash
# Apply and verify PR metadata as a reviewer App (Cody DR or Claudio DR).
# Called by publish-cody-pr-metadata.yml and publish-claudio-pr-metadata.yml.
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${BASE_BRANCH:?BASE_BRANCH is required}"
: "${EXPECTED_AUTHOR:?EXPECTED_AUTHOR is required}"
: "${PUBLISHER_APP_SLUG:?PUBLISHER_APP_SLUG is required}"

expected_app_slug="${EXPECTED_AUTHOR%\[bot\]}"
[[ "$PUBLISHER_APP_SLUG" == "$expected_app_slug" ]] || {
  echo "unexpected metadata publisher: $PUBLISHER_APP_SLUG (expected $expected_app_slug)" >&2
  exit 1
}

jq -e 'if type == "array" then . else error("not an array") end' <<<"${LABELS_JSON:-[]}" >/dev/null || {
  echo "LABELS_JSON is not a valid JSON array" >&2; exit 1
}
jq -e 'if type == "array" then . else error("not an array") end' <<<"${ASSIGNEES_JSON:-[]}" >/dev/null || {
  echo "ASSIGNEES_JSON is not a valid JSON array" >&2; exit 1
}
mapfile -t labels    < <(jq -er '.[] | strings | select(length > 0)' <<<"${LABELS_JSON:-[]}")
mapfile -t assignees < <(jq -er '.[] | strings | select(length > 0)' <<<"${ASSIGNEES_JSON:-[]}")

milestone_number="${MILESTONE_NUMBER:-}"
project_owner="${PROJECT_OWNER:-}"
project_number="${PROJECT_NUMBER:-}"
project_status="${PROJECT_STATUS:-}"

if [[ -n "$project_owner$project_number$project_status" ]]; then
  [[ -n "$project_owner" && -n "$project_number" && -n "$project_status" ]] || {
    echo "project owner, number, and status must be supplied together" >&2
    exit 2
  }
fi

actual_base="$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --json baseRefName --jq .baseRefName)"
[[ "$actual_base" == "$BASE_BRANCH" ]] || {
  echo "base branch mismatch: expected $BASE_BRANCH, got $actual_base" >&2; exit 1
}

for label in "${labels[@]}"; do
  gh pr edit "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --add-label "$label"
done

if [[ -n "$milestone_number" ]]; then
  milestone_title="$(gh api "repos/${GITHUB_REPOSITORY}/milestones/${milestone_number}" --jq .title)"
  gh pr edit "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --milestone "$milestone_title"
fi

for assignee in "${assignees[@]}"; do
  gh pr edit "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --add-assignee "$assignee"
done

if [[ -n "$project_owner" ]]; then
  project_json="$(gh project view "$project_number" --owner "$project_owner" --format json)"
  project_id="$(jq -er '.id' <<<"$project_json")"
  item_json="$(gh project item-add "$project_number" --owner "$project_owner" \
    --url "https://github.com/${GITHUB_REPOSITORY}/pull/${PR_NUMBER}" --format json)"
  item_id="$(jq -er '.id' <<<"$item_json")"
  fields_json="$(gh project field-list "$project_number" --owner "$project_owner" --format json)"
  field_id="$(jq -er '.fields[] | select(.name == "Status") | .id' <<<"$fields_json")"
  option_id="$(jq -er --arg status "$project_status" \
    '.fields[] | select(.name == "Status") | .options[] | select(.name == $status) | .id' \
    <<<"$fields_json")"
  gh project item-edit --id "$item_id" --project-id "$project_id" \
    --field-id "$field_id" --single-select-option-id "$option_id"
fi

observed="$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" \
  --json baseRefName,labels,milestone,assignees,projectItems)"

jq -e --arg base "$BASE_BRANCH" '.baseRefName == $base' <<<"$observed" >/dev/null || {
  echo "metadata verification failed: base branch" >&2; exit 1
}
for label in "${labels[@]}"; do
  jq -e --arg v "$label" 'any(.labels[]; .name == $v)' <<<"$observed" >/dev/null || {
    echo "metadata verification failed: label $label" >&2; exit 1
  }
done
if [[ -n "${milestone_title:-}" ]]; then
  jq -e --arg v "$milestone_title" '.milestone.title == $v' <<<"$observed" >/dev/null || {
    echo "metadata verification failed: milestone $milestone_title" >&2; exit 1
  }
fi
for assignee in "${assignees[@]}"; do
  jq -e --arg v "$assignee" 'any(.assignees[]; .login == $v)' <<<"$observed" >/dev/null || {
    echo "metadata verification failed: assignee $assignee" >&2; exit 1
  }
done
if [[ -n "$project_owner" ]]; then
  jq -e --arg title "$(jq -er '.title' <<<"$project_json")" \
    'any(.projectItems[]; .title == $title)' <<<"$observed" >/dev/null || {
    echo "metadata verification failed: Project item" >&2; exit 1
  }
  gh project item-list "$project_number" --owner "$project_owner" --limit 1000 --format json \
    | jq -e --arg id "$item_id" --arg status "$project_status" \
      'any(.items[]; .id == $id and .status == $status)' >/dev/null || {
    echo "metadata verification failed: Project status $project_status" >&2; exit 1
  }
fi

echo "metadata verified for ${GITHUB_REPOSITORY}#${PR_NUMBER}"
