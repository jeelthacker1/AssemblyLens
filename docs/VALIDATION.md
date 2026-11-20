# Validation record — 20 November 2026

This file distinguishes executed checks from outstanding factory acceptance. No photographed factory dataset or physical assembly was available to this build session.

## Executed checks

| Check | Observed result |
|---|---|
| Python behavioral/API/CV/ONNX/WebRTC/drift tests | 55 passed; one Starlette/httpx deprecation warning |
| Next.js production build | Passed TypeScript, compilation and static page generation on Windows and in Linux Docker |
| Go relay | `go test ./...`, `go vet ./...`, and `go build` completed; relay currently has no Go unit-test cases |
| Docker core stack | API and PostgreSQL healthy; Next.js and RustFS running on local ports |
| Running PostgreSQL/S3 integration | Correct sequence, wrong-order fault, three photograph retrievals and decision endpoint passed using explicitly synthetic pixels |
| Browser UI | Signed in, loaded operator/workflow screens, saved a workflow, created an inspection, and opened history with three evidence images and audit events |
| Camera discovery | No available OpenCV camera found on the build host |
| WebRTC transport | Two actual peer connections transported synthetic video frames to the API and returned pixel-derived detections in an automated test |
| ONNX execution | A test graph derived confidence from input pixel values; black and white inputs produced different real runtime outputs |

The browser initially waited indefinitely for camera permission/device availability. A 15-second timeout and explicit connecting state were added; late-arriving streams are stopped after cancellation/unmount. Real-camera acceptance remains pending.

## Measured performance

Host: Windows 11, Python 3.13.3, OpenCV 4.14.0; the API test used local Docker Linux containers. See JSON for the processor identifier and exact timings. This workstation also ran development/container processes; these are development measurements, not a controlled hardware qualification.

| Measurement | Input/workload | Result |
|---|---|---|
| In-process vision | 200 synthetic 800×480 frames; HSV segmentation plus QR/barcode decoding | 16.66 FPS; p50 59.89 ms; p95 72.81 ms; p99 82.28 ms |
| Central image API | 100 concurrent clients, 3 synthetic JPEG frames each, 300 total | 5.00 FPS overall; p50 7,829 ms; p95 21,233 ms; p99 22,656 ms; zero request errors |
| JPEG example | Synthetic kit image, quality 85 | 10,620 bytes |

Raw reports: [CPU](benchmark-cpu.json), [100-client API](benchmark-api-100.json), [database/evidence integration](smoke-results.json).

**The central-image path does not meet a 100-camera real-time target.** The 100-client run is an overload/concurrency exercise, not 100 physical camera streams. Edge inference reduces image transmission and central CPU work, but a representative distributed-edge soak test is still required. Ten million historical inspections were not loaded or benchmarked.

## Accuracy not measured

There are no honest production values yet for component detection precision/recall, assembly false acceptance/rejection, or uncertain-prediction rate. Unit tests and synthetic masks are insufficient to estimate them. The evaluation tool computes these metrics from independently labeled inspection outcomes; no numbers are fabricated.

FAR = visually accepted known-bad assemblies / all known-bad assemblies. FRR = visually rejected known-good assemblies / all known-good assemblies. Uncertain outcomes are reported separately; they reduce acceptance recall. Empty denominators produce null rather than a perfect score.

## Outstanding acceptance

- Physical USB/RTSP/Basler camera and real photographed kit scenarios.
- Real printed barcode/QR coverage across illumination, motion and focus.
- Camera metrology uncertainty, lens distortion and working-plane repeatability.
- Task-specific detector training, photographed held-out evaluation, calibrated confidence, GPU throughput and INT8 accuracy trade-offs.
- Cross-camera fusion, 100-stream distributed soak, 10M-row history performance and backup/restore exercise.
- Production TLS/SSO/secret rotation, schema migration process, network isolation, HA and operational runbooks qualified for the factory.

See FEATURE_MATRIX.md for capability-by-capability boundaries. Visual predictions do not certify product quality or replace required safety inspections.
