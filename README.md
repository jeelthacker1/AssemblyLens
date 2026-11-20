# AssemblyLens

Visual assembly assistance with a real camera pipeline, configurable workflows, an assembly state machine, retained evidence, and human review.

**Status: functional pilot implementation, not a validated industrial quality system.** The default recognizer segments a reproducible three-color training fixture from real image pixels. It does not identify arbitrary industrial parts without suitable models and training data. See the [feature verification matrix](docs/FEATURE_MATRIX.md) for implementation and validation boundaries.

## Run the full local stack

Requires Docker Desktop/Engine with Linux containers and Python for one-time credential generation.

```sh
python tools/setup_env.py
docker compose up -d --build
```

Open [the console](http://localhost:3010) and connect to `http://localhost:8010` with **`demo-admin`**. Click **Set up training kit**. These known demo keys work only with `DEMO_MODE=1`; the Compose ports bind to localhost. Generated storage/database credentials remain in the ignored `.env` file.

1. Prepare the [physical training kit](docs/KIT.md).
2. Select a station and workflow, enter a unique serial number, and start an inspection.
3. Connect a webcam and allow camera access. No detections are prerecorded or injected into the live pipeline.
4. Place the red base, green bracket, then blue cap in their respective zones. Leave installed parts visible.
5. Install the blue cap first to deliberately trigger an incorrect-order fault.
6. Stop capture, finish the inspection, and open **Inspections → Review**.
7. Inspect the photographs, supply a decision reason, and approve, reject, or request rework. An administrator can explicitly override with an audited reason.

The browser requires localhost or HTTPS for camera access. A machine without a camera can run the software and automated tests but cannot complete the physical validation exercise.

## Development without Docker

Python 3.13 and Node.js 22+ are used by CI. From the repository root:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.lock
```

Set `DEMO_MODE=1` in your shell, then run:

```sh
uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

In another shell:

```sh
cd web
npm ci
npm run dev
```

SQLite and filesystem evidence are the development defaults. Docker uses PostgreSQL and S3-compatible RustFS storage. [API documentation](http://localhost:8010/docs) documents all request schemas.

## Edge cameras

```sh
python -m edge.agent --discover
# Set ASSEMBLYLENS_API_KEY in the environment. For a local demo: demo-edge.
python -m edge.agent --source 0 --camera CAMERA_RECORD_ID --inspection INSPECTION_ID
```

For RTSP, set `CAMERA_SOURCE=rtsp://...` privately on the gateway and omit `--source`. Do not commit credentials. For Basler cameras install `pypylon` and the vendor runtime, then use `--driver pylon --source CAMERA_SERIAL`. Other GenICam vendors need their own tested adapters; there is no claim of universal industrial-camera support.

The agent performs local inference, keeps one queued frame, reconnects with backoff, limits sampling, and sends compressed event photographs selectively. `--clips` retains up to 100 short pre-event clips locally. It does not continuously upload video or remotely control machinery. One authoritative camera is bound to each inspection; multiple station cameras can run separate inspections.

## Models and training

```sh
pip install -r requirements-ml.txt
python -m tools.train_detector annotations.xml photographed_images --epochs 20 --device cpu --output data/detector
python -m tools.evaluate reviewed_inspections.jsonl
python -m tools.quantize data/detector/detector.onnx data/detector/quantized.onnx photographed_images --labels '["base","bracket","cap"]'
```

`tools.train_detector` trains a PyTorch Faster R-CNN detector from CVAT image boxes, reports held-out detection precision/recall, and exports decoded ONNX boxes. `tools.train` is a separate crop-classification research baseline. Training has to be run on real representative data; no production-trained model or measured factory accuracy is bundled. Keep entire products/capture sessions in one split to avoid leakage; the supplied image-level split is only a baseline.

The ONNX runtime contract is fixed-size RGB NCHW float32 in `[0,1]`, with output `[1,N,6]`: `x1,y1,x2,y2,score,class_index`, pixel boxes in the model input coordinate system, NMS already applied. Orientation is not provided by this detector contract. Use color-mask orientation for the kit, or implement a validated keypoint/pose adapter for asymmetric factory parts.

Register models in the console, record validation and a deployment reason, then set a station's `active_model_id` or `shadow_model_id` through the station API. Shadow predictions never advance the assembly state. The edge supports explicit `--model`, `--shadow-model`, `--labels`, and CPU/GPU profiles. CUDA requires the matching `onnxruntime-gpu` package and driver stack instead of CPU ONNX Runtime.

## Verification

```sh
python -m pytest -q
cd web
npm run build
# from relay/: go test ./... && go vet ./... && go build ./...
```

```sh
python -m tools.benchmark --synthetic --iterations 200
# Actual photographed benchmark:
python -m tools.benchmark --images photographed_images --iterations 200
# Concurrent API exercise; creates clearly named BENCH-* inspections:
python -m tools.benchmark --synthetic --api http://localhost:8010 --concurrency 100 --iterations 3 --output docs/benchmark-api.json
```

Use `ASSEMBLYLENS_API_KEY` for API benchmarks. Synthetic engineering test frames are explicitly labeled and do not establish precision, recall, FAR, or FRR on real manufacturing data.

## Repository map

| Path | Purpose |
|---|---|
| `web/` | Next.js, TypeScript, Tailwind operator and engineering console |
| `backend/` | FastAPI, state machine, PostgreSQL/SQLite persistence, vision, evidence, RBAC |
| `edge/` | USB/RTSP/Basler capture, local inference, reconnect, bounded buffers |
| `relay/` | Go transactional outbox relay to Kafka, ClickHouse and Redis |
| `tools/` | Dataset/training/evaluation/quantization/benchmark tools |
| `tests/` | Behavioral state-machine, API, CV, isolation and import tests |
| `infra/` | ClickHouse schema and Kubernetes deployment foundation |
| `docs/` | Plan, matrix, kit, architecture, operations and measured results |

See [implementation plan](docs/PLAN.md), [architecture](docs/ARCHITECTURE.md), [operations](docs/OPERATIONS.md), and [validation record](docs/VALIDATION.md).

**Safety boundary:** predictions assist operators. They do not guarantee product quality, prove torque or hidden connections, replace required safety inspections, or authorize autonomous machinery control.
