# Feature verification matrix

Implemented means source exists with the stated boundaries. Tested means the specific test was run; it does not imply industrial qualification. Consult VALIDATION.md for current execution results.

| # | Requested module | Implementation | Verification and remaining boundary |
|---|---|---|---|
| 1 | Real cameras | Browser getUserMedia; OpenCV USB/RTSP; optional Basler pylon | No camera discovered on build host; physical/vendor validation pending |
| 2 | Discovery/configuration/calibration/health | Edge discovery, camera records, planar homography, heartbeat, reconnect | Calibration math tested; lens distortion and metrology uncertainty certification not implemented |
| 3 | Multi-camera stations | Multiple camera records and edge processes per station | Separate inspections supported; cross-view synchronization/fusion not implemented |
| 4 | Workflow designer | Ordered steps, editable instructions, draggable/resizable zones | Frontend production build; server workflow validation tests |
| 5 | Product variants/BOM | Workflow variants, distinct parts, snapshot per inspection | Snapshot and unique-ID tests; nested BOM/ERP revision reconciliation not implemented |
| 6 | Visual instructions | Current-step panel, normalized zone and detection overlays | Browser console implementation; camera acceptance pending |
| 7 | Detection/segmentation/tracking | Real HSV masks/contours, centroid tracker, ONNX box detector | Controlled-pixel CV tests; generic learned segmentation and robust occlusion tracking not supplied |
| 8 | Presence/placement/orientation/sequence | Full-box zone containment, undirected angle modulo 180, stable-frame state machine | Behavioral tests; 3D/directed pose, hidden attachments and torque are outside scope |
| 9 | QR/barcodes | OpenCV QR and barcode decoder output | Decoder invoked in pipeline; real printed-code coverage pending |
| 10 | Inspection zones | Normalized rectangles, visual editor and server validation | Bounds and placement tests; polygonal inspection zones not implemented |
| 11 | Reference images | ORB matching with RANSAC homography API | Textured match and insufficient-texture tests |
| 12 | Measurement | Four-point planar calibration and point distance API | Known geometry test; no accuracy claim beyond separately validated calibrated plane |
| 13 | Operator feedback | Live status, progress, faults, latency, detections | Connected to real API; no simulated live detection fallback |
| 14 | Missing/wrong part alerts | Installed-part removal, unknown model label, wrong order/placement | State tests; HSV cannot reliably distinguish lookalike substitutions |
| 15 | Uncertain review | Needs-review state; evidence-backed active-learning queue | API and state tests; scores are not calibrated probabilities |
| 16 | Approve/reject/rework | Role checks, reason, optimistic version, audit | End-to-end API tests |
| 17 | Serial traceability | Tenant-unique serial, inspection history and CSV | Duplicate-serial test |
| 18 | Photo/video evidence | Event JPEGs with SHA256, S3 or local; optional bounded local event clips | Photo retrieval/isolation tests; video upload/catalog UI not implemented |
| 19 | Analytics/trends | Latest-1000 operational summary; CSV; ClickHouse event schema and relay | Real database summaries; long-range dashboard queries not yet wired to ClickHouse |
| 20 | Model lifecycle | CVAT box/polygon imports, immutable dataset IDs/checksums, PyTorch scripts, ONNX registry, validation gate and deployment history | Import and bad-model tests; factory-data training and trained-export qualification pending |
| 21 | Active learning | Uncertain/fault transitions create prioritized annotation candidates | Queue endpoint and UI; external CVAT job creation is manual |
| 22 | Drift/lighting | Brightness baseline deviation; rolling confidence-distribution PSI against an explicit baseline; shadow comparison | Distribution math/warmup/shift tests; requires representative station baseline; a drift alert is not proof of quality loss |
| 23 | MES integration | Authenticated REST/OpenAPI, serials, CSV, transactional event outbox | API tests and Go compile/vet; vendor-specific MES connector not supplied |
| 24 | Multi-factory/tenant | Factory/station hierarchy, tenant-qualified DB lookups, scoped API identities | Cross-tenant tests; SSO and database row-level-security policy not implemented |
| 25 | Audit/permissions/reports | Append-only API events, roles, decision reasons, CSV formula neutralization | RBAC tests; DB-superuser tamper protection and signed compliance reports not implemented |

## Advanced requirements

| Capability | Delivered behavior | Qualification boundary |
|---|---|---|
| Edge inference | OpenCV or ONNX inference at capture gateway | Deploy and profile on chosen hardware |
| CPU/GPU | CPU default; explicit CUDA provider check | GPU hardware not available in validation environment |
| Async/bounded processing | Dedicated capture thread, one latest frame, one request in flight | Driver reads can block; RTSP timeout depends on OpenCV/backend |
| Adaptive sampling | Latency naturally lowers processing FPS; stale frames dropped | Not a fleet-wide adaptive controller |
| Compression/retention | JPEG events, bounded MPEG-4 clips, S3 90-day lifecycle | Retention policy must match factory obligations |
| Quantization | Dynamic INT8 tool with measured set agreement and latency | Operator support and ground-truth accuracy must be validated per model |
| Shadow rollout | Alternate predictions logged without changing verification | No automated promotion or fleet rollout controller |
| Provenance | Workflow snapshot/hash, model SHA, dataset SHA, frame sequence, evidence SHA, actor | External ground-truth report authenticity remains an engineering responsibility |
| WebRTC | Optional authenticated SDP endpoint and browser mode | Same LAN by default, bounded peers; TURN/NAT deployment not implemented |
| 100+ cameras / 10M inspections | Distributed edge architecture and benchmark tooling | Not demonstrated at physical target scale; no unsupported scale claim |
