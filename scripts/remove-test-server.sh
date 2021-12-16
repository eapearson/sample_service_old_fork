root=$(git rev-parse --show-toplevel)

# if [ -z "$ENV" ]; then
# 	echo "The 'ENV' environment variable is required, set to either ci, next, appdev, or prod"
# 	exit 1
# fi
# echo "Starting SampleService for environment '${ENV}'"


# if [ -z "$GITHUB_TOKEN" ]; then
# 	echo "The 'GITHUB_TOKEN' environment variable is required"
# 	exit 1
# fi
# export github_token=${GITHUB_TOKEN}
# echo "GITHUB_TOKEN is set"

# if [ -z "$SPECS_GITHUB_REPO" ]; then
# 	echo "The 'SPECS_GITHUB_REPO' environment variable is required"
# 	exit 1
# fi
# export specs_github_repo=${SPECS_GITHUB_REPO}
# echo "specs_github_repo is set to ${specs_github_repo}"


# # export specs_github_branch={$SPECS_BRANCH:-master}
# if [ -z "$SPECS_GITHUB_BRANCH" ]; then
# 	echo "The 'SPECS_GITHUB_BRANCH' environment variable is required"
# 	exit 1
# fi
# export specs_github_branch=${SPECS_GITHUB_BRANCH}
# echo "specs_github_branch is set to ${specs_github_branch}"


if [ -z "$MOCK_DATASET_PATH" ]; then
	echo "The 'MOCK_DATASET_PATH' environment variable is required"
	exit 1
fi
echo "MOCK_DATASET_PATH is set to ${MOCK_DATASET_PATH}"

docker compose rm -f
