uvicorn app.main:app

python -m app.embedding_index

docker build --no-cache -t movie-recommender:latest .


# Tag your local image for Artifact Registry
docker tag movie-recommender:latest \
  asia-southeast1-docker.pkg.dev/int-data-livedocs/livedocs-repo/movie-recommender:latest

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker asia-southeast1-docker.pkg.dev

# Push the local image
docker push asia-southeast1-docker.pkg.dev/int-data-livedocs/livedocs-repo/movie-recommender:latest



gcloud run deploy movie-recommender-service \
  --image asia-southeast1-docker.pkg.dev/int-data-livedocs/livedocs-repo/movie-recommender:latest \
  --region asia-southeast1 \
  --port 8000 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --allow-unauthenticated \
  --execution-environment gen2 \
  --set-env-vars PYTHONUNBUFFERED=1,SESSION_SECRET="super-secret-key"
