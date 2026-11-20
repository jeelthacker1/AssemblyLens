# Reproducible physical assembly kit

This is a low-risk visual training fixture, not a certified manufacturing inspection.

## Materials

- A matte white board or A4 landscape sheet, rigid enough to stay flat.
- Three matte rectangular pieces: red, green and blue. Colored card or plastic blocks work. Avoid glossy pieces.
- Optional removable hook-and-loop dots to make placing/removing parts resemble assembly.
- A fixed USB webcam, diffused lighting, and a ruler if exploring planar measurements.
- Print `kit-board.svg` at 100%. It is a placement guide, not a calibration certificate.

## Camera setup

1. Mount the camera overhead; keep the board parallel to the sensor and fill the image with the board.
2. In the live view, place the red piece inside the left inspection rectangle, green inside the middle, blue inside the right. Each piece should occupy roughly 10–15% of image width and 20–30% of height, entirely inside its zone.
3. Use **Workflows & BOM** to adjust zones if framing differs. Do not move the camera after calibration.
4. HSV thresholds are starting values, not universally valid color definitions. Adjust for the actual lighting and camera. The default red interval covers hue 0–12, not all red shades near hue 179.

## Acceptance scenarios

| Scenario | Action | Expected behavior |
|---|---|---|
| Correct sequence | Start empty, place red, wait for confirmation, place green, then blue; keep all visible | Progress advances after three stable frames; final state awaits human approval |
| Incorrect ordering | Start empty, place blue first and keep it visible for three frames | Incorrect-order fault latches; ordinary approval blocked |
| Omitted step | Place only red, stop camera and finish | Green and blue reported omitted |
| Repeated step | Place red, wait for completion, remove it for three frames, reinstall it | Missing-component and repeated-step faults |
| Misplacement | Move a part across a zone boundary | Placement uncertainty/review; step does not advance |
| Orientation | Configure a 0° long-axis target, place a long rectangular part vertically | Orientation review; 180° ambiguity is unavoidable with symmetric rectangles |
| Occlusion | Cover an installed part for three frames | Missing-component review; no automatic approval |
| Lighting shift | Substantially change illumination after baseline | Review due to lighting drift; validate threshold locally |
| Rework | Reviewer records a reason and starts rework; remove all pieces and restart | New sequence state; previous events remain in history |

Photograph each scenario with product serial, station, camera, lighting, model/workflow version and independent expected outcome. Collect variations across sessions. Store raw data outside the public repository; avoid operator faces and proprietary factory material in public uploads.

## What this kit cannot establish

Color detection does not prove mechanical engagement, fastener torque, internal wiring, material identity, or product safety. A green object of the wrong shape may pass the color rule. Industrial adoption requires task-specific data, validated part/pose models, and required human/safety inspections.
