#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?}"; : "${GITHUB_REPOSITORY:?}"; : "${PR_NUMBER:?}"; : "${REVIEW_EVENT:?}"; : "${REVIEW_BODY:?}"; : "${EXPECTED_AUTHOR:?}"
readonly inline_comments_json="${INLINE_COMMENTS_JSON:-[]}"
readonly replies_json="${REPLIES_JSON:-[]}"
readonly resolve_thread_ids_json="${RESOLVE_THREAD_IDS_JSON:-[]}"
[[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]] || { echo "invalid PR number" >&2; exit 1; }
case "$REVIEW_EVENT" in APPROVE) expected_state=APPROVED ;; COMMENT) expected_state=COMMENTED ;; REQUEST_CHANGES) expected_state=CHANGES_REQUESTED ;; *) echo "invalid review event" >&2; exit 1 ;; esac
jq -e 'type == "array" and all(.[]; type == "object" and (.path | type == "string" and length > 0) and (.line | type == "number" and floor == . and . > 0) and (.body | type == "string" and length > 0))' <<<"$inline_comments_json" >/dev/null || { echo "invalid inline_comments_json" >&2; exit 1; }
jq -e 'type == "array" and all(.[]; type == "object" and (.comment_id | type == "number" and floor == . and . > 0) and (.body | type == "string" and length > 0))' <<<"$replies_json" >/dev/null || { echo "invalid replies_json" >&2; exit 1; }
jq -e 'type == "array" and all(.[]; type == "string" and length > 0)' <<<"$resolve_thread_ids_json" >/dev/null || { echo "invalid resolve_thread_ids_json" >&2; exit 1; }
readonly expected_pr_url="https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}"
while IFS= read -r reply; do
  comment_id="$(jq -r '.comment_id' <<<"$reply")"
  [[ "$(gh api "repos/${GITHUB_REPOSITORY}/pulls/comments/${comment_id}" --jq .pull_request_url)" == "$expected_pr_url" ]] || { echo "reply target mismatch" >&2; exit 1; }
  [[ -z "$(gh api "repos/${GITHUB_REPOSITORY}/pulls/comments/${comment_id}" --jq '.in_reply_to_id // empty')" ]] || { echo "reply target must be top-level" >&2; exit 1; }
done < <(jq -c '.[]' <<<"$replies_json")
while IFS= read -r thread_id; do
  [[ "$(gh api graphql -f query='query($thread: ID!) { node(id: $thread) { ... on PullRequestReviewThread { pullRequest { number } } } }' -f thread="$thread_id" --jq '.data.node.pullRequest.number')" == "$PR_NUMBER" ]] || { echo "resolution target mismatch" >&2; exit 1; }
done < <(jq -r '.[]' <<<"$resolve_thread_ids_json")
head_sha="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}" --jq .head.sha)"
jq -n --arg event "$REVIEW_EVENT" --arg body "$REVIEW_BODY" --arg commit_id "$head_sha" --argjson comments "$inline_comments_json" '{event: $event, body: $body, commit_id: $commit_id} + (if ($comments | length) == 0 then {} else {comments: ($comments | map({path, line, side: "RIGHT", body}))} end)' > review.json
gh api --method POST "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews" --input review.json > created-review.json
[[ "$(jq -r '.user.login' created-review.json)" == "$EXPECTED_AUTHOR" ]] || { echo "unexpected review author" >&2; exit 1; }
[[ "$(jq -r '.pull_request_url' created-review.json)" == "$expected_pr_url" ]] || { echo "review target mismatch" >&2; exit 1; }
[[ "$(jq -r '.state' created-review.json)" == "$expected_state" ]] || { echo "unexpected review state" >&2; exit 1; }
while IFS= read -r reply; do
  comment_id="$(jq -r '.comment_id' <<<"$reply")"; reply_body="$(jq -r '.body' <<<"$reply")"
  gh api --method POST "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments" -f body="$reply_body" -F in_reply_to="$comment_id" > reply.json
  [[ "$(jq -r '.user.login' reply.json)" == "$EXPECTED_AUTHOR" ]] || { echo "unexpected reply author" >&2; exit 1; }
done < <(jq -c '.[]' <<<"$replies_json")
while IFS= read -r thread_id; do gh api graphql -f query='mutation($thread: ID!) { resolveReviewThread(input: {threadId: $thread}) { thread { isResolved } } }' -f thread="$thread_id" --jq '.data.resolveReviewThread.thread.isResolved' | grep -qx true; done < <(jq -r '.[]' <<<"$resolve_thread_ids_json")
printf 'Publication report: review=1 inline=%s replies=%s resolutions=%s\n' "$(jq length <<<"$inline_comments_json")" "$(jq length <<<"$replies_json")" "$(jq length <<<"$resolve_thread_ids_json")"
