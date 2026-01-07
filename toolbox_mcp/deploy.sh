#!/bin/bash
set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${GOOGLE_CLOUD_LOCATION:-us-central1}
SERVICE_NAME="toolbox-mcp"

# Build and push container
gcloud builds submit --tag gcr.io/${PROJECT_ID}/${SERVICE_NAME}

# Deploy to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT_ID}/${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT_ID}

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo "Toolbox MCP deployed at: ${SERVICE_URL}"
echo "Set TOOLBOX_MCP_URL=${SERVICE_URL} in .env"
