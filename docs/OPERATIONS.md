# Operations

## Local services

`python tools/setup_env.py` creates random database/object-store credentials and an administrator key in `.env`, without printing secrets or overwriting an existing file. The default local demo uses `DEMO_MODE=1`. The console is at localhost:3010 and the API at localhost:8010. Object-storage console is localhost:9001. Change host ports with API_PORT and WEB_PORT, and update NEXT_PUBLIC_API_URL/CORS_ORIGINS together before rebuilding the web image.

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 api web
docker compose stop
```

`stop` preserves volumes. Do not remove volumes unless you intend to delete inspection and evidence data.

The local S3 provider is RustFS, pinned by image digest after pull verification. The initial MinIO image choice was replaced because the upstream prebuilt-image distribution is unavailable. Provider references: [MinIO repository status](https://github.com/minio/minio), [official RustFS Docker instructions](https://github.com/rustfs/docs.rustfs.com/blob/main/content/en/installation/container/docker.md). The application itself uses the standard S3 API through boto3 and can point to another compatible provider.

## Scale profile

Set `ENABLE_OUTBOX=1` in `.env` and start:

```sh
docker compose --profile scale up -d --build
```

This enables Kafka, Redis, ClickHouse and the Go relay. The single-broker Compose topology is for development, not high availability. Monitor outbox backlog and oldest pending age, Kafka consumer lag, ClickHouse write errors, API p95/p99, rejected observations, S3 failures, and edge heartbeat age. Relay `/metrics` exports delivered event count inside the network; `/health` checks database reachability.

For MLflow:

```sh
docker compose --profile ml up -d mlflow
python -m tools.train_detector annotations.xml photographed_images --mlflow http://localhost:5000
```

The local MLflow server is not an authenticated production service. Keep it loopback-only or provide the appropriate identity gateway.

## Production identity

Disable demo authentication and provision separate random keys in `API_KEYS_JSON`:

```json
{"<random-key>":{"tenant":"factory-a","user":"gateway-01","role":"edge"}}
```

Supported roles: admin, engineer, operator, reviewer, edge, viewer. Rotate keys through deployment secrets. Do not commit the secret JSON or put credentials into RTSP URLs in camera records. The edge gateway may read a private CAMERA_SOURCE environment variable. Use TLS termination, request size limits, rate limits, network policy and service-specific credentials before network exposure. The API has no SSO or user provisioning UI.

## Kubernetes

`infra/kubernetes.yaml` is a deployment foundation, not a self-contained production cluster. Replace image references with the built commit digest. Create namespace `assemblylens` and secret `assemblylens-runtime` containing DATABASE_URL, API_KEYS_JSON, DEMO_MODE=0, CORS_ORIGINS, S3_ENDPOINT, S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_DEFAULT_REGION. Provision the bucket and lifecycle separately. Apply the manifest, then provide TLS ingress for the console and API.

The API uses one replica and a persistent volume for model artifacts. Before scaling replicas, use shared model artifact storage, remove redundant global mutation serialization around inference, provide migration orchestration, and test PostgreSQL locking under load. `Base.metadata.create_all` initializes the pilot schema; schema evolution requires a reviewed migration workflow before production updates.

## Retention, backup and recovery

- Event photographs are retained selectively, not per frame. S3 lifecycle expires them after 90 days in Compose.
- Local filesystem evidence has no automatic age deletion; choose S3 lifecycle or deploy an explicit retention job.
- Optional edge clips are local and bounded to the newest 100 files. They are not a central video archive.
- Back up PostgreSQL and object storage on coordinated schedules. Verify restoration of serial history, evidence hashes and model artifacts.
- Outbox rows are retained after delivery; schedule an audited purge/archive only after consumer retention obligations are satisfied.
- Audit history is append-only through the API, not tamper-proof against privileged database administrators.

## WebRTC and edge recovery

The locked development environment includes aiortc; minimal installs can use requirements-webrtc.txt. Select WebRTC in the operator console for a same-LAN peer connection. Peers are bounded to 4 per tenant and 16 per process, expire after 30 minutes, and close on disconnection. Containers/NAT may require host networking or an explicitly configured TURN deployment, which is not bundled. Sampled JPEG transport remains available.

The edge reconnects failed captures with exponential backoff up to 30 seconds. RTSP uses explicit 5-second open/read timeouts when supported by FFmpeg. Loss of API connectivity never generates an approval; the frame queue remains bounded and failure is logged. Network observations have monotonic sequences; stale requests are rejected and the edge reloads state.

## Source documentation consulted

- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/)
- [Next.js installation and system requirements](https://nextjs.org/docs/app/getting-started/installation)
