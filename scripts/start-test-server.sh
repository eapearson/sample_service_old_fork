root=$(git rev-parse --show-toplevel)

if [ -z "$MOCK_DATASET_PATH" ]; then
	echo "The 'MOCK_DATASET_PATH' environment variable is required"
	exit 1
fi
echo "MOCK_DATASET_PATH is set to ${MOCK_DATASET_PATH}"

docker compose up
