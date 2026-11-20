# Implementation plan and acceptance gates

The original request spans a factory software product, camera hardware, training data, deployment operations, and physical validation. This repository implements a runnable pilot and records the remaining validation work explicitly.

| Increment | Deliverables | Acceptance gate |
|---|---|---|
| 1. Domain and identity | Tenant-scoped persistence, RBAC, immutable inspection workflow snapshots, serial tracking | Cross-tenant reads denied; duplicate serial and stale review version rejected |
| 2. Real image path | Camera capture, OpenCV segmentation, frame ingestion, zones/orientation, retained photographs | Real pixel pipeline tested with controlled images; physical camera acceptance remains required |
| 3. State machine | Stable observations, correct order, omitted/repeated/uncertain/missing parts, override/rework | Behavioral unit tests and API decision/evidence tests |
| 4. Operator and engineering UI | Camera console, draggable zones, BOM/variants, review queue, analytics, registry/import | TypeScript production build and browser UI inspection |
| 5. Edge and transport | Latest-frame queue, reconnection, RTSP/USB/Basler adapter, ONNX CPU/GPU, optional WebRTC | Hardware-specific acceptance; WebRTC loopback test where dependencies available |
| 6. Lifecycle and integration | CVAT import, detector training/export, metrics, shadow, quantization, Go outbox | Compile/test relay; validate model artifacts on held-out photographed data |
| 7. Deployment | Compose PostgreSQL/S3, optional Kafka/ClickHouse/Redis/MLflow, Kubernetes foundation | Boot local stack; inspect readiness and integration behavior |
| 8. Scale and factory acceptance | Benchmark tools, retention estimates, concurrent-client exercise | Real 100-stream soak, 10M-row benchmark, GPU and photographed acceptance are required before production claims |

## Definition of physical acceptance

- Use the kit instructions with an actual connected camera, not software-injected detections.
- Photograph complete assemblies, omissions, substitutions, rotated components, wrong ordering, occlusions, glare, and camera motion.
- Label outcomes independently of the model. Split by assembly/session, not adjacent frames.
- Show correct steps advancing, incorrect order latching, uncertain observations remaining unapproved, and evidence retrievable after restart.
- Test reviewer and administrator decisions with a recorded reason, plus unauthorized and cross-tenant denial.
- Measure precision, recall, false acceptance, false rejection, uncertainty, end-to-end p50/p95/p99 latency, storage growth, disconnection recovery, and frame replacement rate.
- Accept only against thresholds set by the factory's quality engineering team for the intended task.

No physical acceptance is inferred from synthetic unit tests or successful builds.
