# Court Deployment MVP Requirements

## Problem Statement

The current project is a local video analysis script that works on pre-recorded badminton videos. It requires manual file selection, manual template selection, and interactive court annotation during each run. This is useful for offline analysis, but it is not suitable for stable court-side deployment in a badminton venue.

We need to evolve the project into a deployable court-side system that can be installed near a badminton court, continuously ingest video from fixed cameras, perform local analysis, and provide operational outputs for coaches, venue operators, or players.

## Goal

Build a deployable MVP for a single badminton court that can:

- run on a local edge computer near the court,
- ingest one or more fixed camera streams,
- perform local player and shuttlecock analysis,
- maintain reusable court calibration,
- expose a local operator workflow,
- provide a simple local dashboard and structured outputs,
- recover cleanly from process restarts.

## Scope

### In Scope for MVP

- Single-court deployment
- Fixed camera installation
- Local edge inference on one machine
- Pre-match or one-time court calibration workflow
- Live or near-real-time stream ingestion
- Local analysis session management
- Local web dashboard for operator use
- Local storage of analysis outputs
- Health and status visibility
- Restart-safe configuration and session persistence

### Out of Scope for MVP

- Multi-court scheduling and orchestration
- Cloud-first architecture
- Automatic court keypoint detection
- Production-grade user account system
- Billing, payments, or SaaS tenant management
- Advanced stroke classification
- Accurate line-calling or umpire-grade adjudication
- Fully automatic multi-camera 3D reconstruction
- Mobile app as the primary operator interface

## Deployment Assumptions

- The system is installed on a dedicated edge computer placed near one badminton court.
- Cameras are mounted in fixed positions and do not move during normal operation.
- The venue has a local network available for cameras and dashboard access.
- Local inference is preferred over cloud inference due to latency and privacy.
- An operator can perform initial calibration during installation.
- The system should remain useful even if internet access is unavailable.

## Target Users

### Venue Operator

Needs to start and stop court sessions, check system health, verify camera status, and retrieve match outputs.

### Coach or Analyst

Needs player movement heatmaps, trajectories, rally segmentation, and downloadable analysis data.

### Installer or Maintainer

Needs a stable calibration workflow, configuration persistence, logs, and easy restart behavior.

## User Stories

1. As a venue operator, I want to register the court and connected cameras once so that I do not need to reconfigure the system before each match.
2. As an installer, I want to calibrate the court from the deployed camera view so that analysis uses stable court coordinates.
3. As a venue operator, I want to start a new analysis session from a browser so that I can run the system without terminal commands.
4. As a venue operator, I want to see whether cameras are online and whether inference is running so that I can detect failures quickly.
5. As a coach, I want to view near-real-time overlays and basic match statistics so that I can observe the session while it is running.
6. As a coach, I want to download post-session outputs such as annotated video, JSONL detections, and heatmaps so that I can review the session later.
7. As a maintainer, I want the system to resume with saved configuration after restart so that deployment is robust in real venues.

## Functional Requirements

### FR1. Court Registration and Device Configuration

The system shall allow an operator to define a court profile that stores:

- court name or identifier,
- camera source configuration,
- model paths,
- language and visualization preferences,
- storage locations,
- calibration data.

### FR2. Camera Ingestion

The system shall ingest video from one or more configured fixed camera sources.

MVP baseline:

- one primary camera source is required,
- an RTSP URL or local USB camera source is acceptable,
- optional secondary camera sources may be configured but are not required for the first working version.

### FR3. Calibration Workflow

The system shall provide a reusable court calibration workflow based on a captured camera frame.

The calibration workflow shall:

- capture or upload a calibration image from the installed camera,
- allow an operator to mark court corners,
- save the calibration for reuse,
- support recalibration when the camera position changes.

### FR4. Session Lifecycle

The system shall support a session lifecycle with:

- idle,
- preparing,
- running,
- stopped,
- failed.

An operator shall be able to:

- create a session,
- start analysis,
- stop analysis,
- review session status,
- view session outputs after completion.

### FR5. Live Analysis Pipeline

The system shall run the existing analysis pipeline, adapted for stream or continuous frame ingestion.

The MVP pipeline shall support:

- player pose detection,
- shuttlecock detection,
- court coordinate mapping,
- player tracking,
- rally segmentation,
- movement statistics,
- structured output generation.

### FR6. Dashboard

The system shall expose a local web dashboard for operators.

The MVP dashboard shall provide:

- system status,
- camera status,
- court calibration status,
- session controls,
- current session summary,
- links to output artifacts,
- recent logs or errors.

### FR7. Output Management

The system shall store outputs per session in a predictable directory layout.

Outputs shall include, when available:

- annotated output video,
- session metadata,
- detections JSONL,
- position visualizations,
- calibration artifacts,
- runtime logs.

### FR8. Restart and Recovery

The system shall persist configuration and calibration data so that a process restart does not require full re-setup.

If the process stops unexpectedly, the system shall preserve:

- saved court configuration,
- saved camera configuration,
- prior sessions and artifacts,
- enough runtime state to mark the interrupted session as failed or incomplete.

### FR9. Operator Safety and Maintainability

The system shall avoid requiring terminal interaction for normal operation after installation.

The system shall surface clear operator-facing errors for:

- camera unavailable,
- missing model file,
- invalid calibration,
- output write failure,
- analysis process crash.

## Non-Functional Requirements

### NFR1. Local-First Operation

The system shall remain operable on a local network without requiring internet connectivity during normal session use.

### NFR2. Deployability

The system shall be runnable through a single deployment entrypoint suitable for an edge machine.

Example acceptable forms for MVP:

- `docker compose up`,
- one installer script plus one service start command,
- a packaged local service with a web UI.

### NFR3. Performance

The system shall provide near-real-time feedback for a single court on suitable hardware, even if full-frame processing lags behind true real time.

For MVP, acceptable behavior is:

- live status updates within a few seconds,
- continuous processing without frequent crashes,
- graceful degradation when hardware is slower than target frame rate.

### NFR4. Observability

The system shall emit structured logs and store enough information to diagnose failures after deployment.

### NFR5. Privacy

The system shall store video and analysis data locally by default.

## Constraints

- The current codebase is Python-first and should remain the core inference runtime for MVP.
- The existing offline logic should be reused where practical instead of fully rewritten.
- The deployed system should separate long-running analysis work from the UI process.
- The design should allow future extension to multi-court and cloud sync without forcing them into MVP.

## Risks

- Shuttlecock detection quality may not be reliable enough for all venues and lighting conditions.
- Rally segmentation based on template matching may be too brittle for live deployment.
- Real-time performance will depend heavily on hardware and camera resolution.
- Interactive calibration and template dependence may create operator friction unless the workflow is simplified.

## Acceptance Criteria

### AC1. Installation and Setup

- When a fresh edge machine starts the system for the first time, the system shall allow an operator to create a court profile without editing source code.
- When the operator saves camera and model settings, the system shall persist them for later restarts.

### AC2. Calibration

- When the operator enters calibration mode, the system shall show a frame from the configured camera or an uploaded calibration image.
- When the operator marks the required court corners, the system shall save calibration data for reuse in later sessions.
- When calibration data already exists, the system shall reuse it unless the operator explicitly recalibrates.

### AC3. Session Start

- When the operator starts a session from the dashboard, the system shall transition the session into a preparing or running state without requiring terminal commands.
- When required prerequisites are missing, the system shall block session start and show a clear error message.

### AC4. Live Processing

- While a session is running, the system shall ingest frames from the configured camera source and execute the analysis pipeline on those frames.
- While analysis is running, the system shall update session status and progress information in the dashboard.

### AC5. Artifact Generation

- When a session completes successfully, the system shall store session artifacts in a dedicated session directory.
- When detections are generated, the system shall save structured detection data in a machine-readable format.
- When visualization generation is enabled, the system shall save court-position visualizations for the completed session.

### AC6. Failure Handling

- When the camera source becomes unavailable during a session, the system shall mark the session as failed or degraded and show the reason in the dashboard.
- When the analysis worker crashes, the system shall retain logs and show a recoverable error state instead of silently stopping.

### AC7. Restart Recovery

- When the system process restarts, the system shall reload saved court configuration and calibration data.
- When interrupted sessions exist after restart, the system shall show them as incomplete or failed rather than losing them.

## MVP Deliverables

The first deployable version should include:

- a local backend service,
- a local web dashboard,
- a persistent configuration store,
- a calibration flow,
- a session runner that wraps the existing analysis pipeline,
- per-session artifact storage,
- deployment instructions for an edge machine.

## Future Versions

Later versions may add:

- automatic court detection,
- better shuttlecock models,
- stroke and tactic classification,
- multi-camera fusion,
- multi-court management,
- cloud sync and remote monitoring,
- mobile viewing experiences.
