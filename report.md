# Image Analysis and Segmentation Platform Development Report

## Overview

Image Analysis and Segmentation Platform is a full-stack image upload and processing platform built through multiple development cycles. Over the course of the project, it evolved from a frontend-only prototype into a more complete system with a FastAPI backend, persistent storage, authenticated admin and user workflows, sensitivity-aware file handling, and automatic image segmentation.

This document combines the key ideas, implementation milestones, and lessons from the project's research notes, iterative reports, and final summary into one GitHub-friendly report.

## Project Goal

The goal of the project was to build a practical image-processing workflow that could:

- accept image uploads through a browser interface
- create and track processing jobs
- store results and metadata persistently
- support secure admin and user access patterns
- generate useful segmentation artifacts automatically at upload time

The project also served as a way to demonstrate full-stack development across frontend UX, backend APIs, storage design, authentication, and lightweight computer vision.

## Development Timeline

### Phase 1: Frontend Workflow Prototype

The project started as a frontend-first prototype using HTML, CSS, and vanilla JavaScript. The main goal in this phase was to validate the user workflow before a real backend existed.

Key outcomes:

- built separate pages for Upload, Jobs, Results, and Admin views
- added local image preview before upload
- created a mock API layer with `localStorage`
- simulated job creation, status transitions, and result rendering
- defined the basic API contract that the backend would later implement

This phase made it possible to validate the user experience early and shaped the eventual backend request and response formats.

### Phase 2: Real Backend and Persistent Storage

The next major step replaced the mock data flow with a real FastAPI backend using SQLModel and SQLite. This phase established the first complete end-to-end version of the application.

Key outcomes:

- implemented `POST /api/images` for uploads
- implemented `POST /api/jobs` for background processing
- added `GET /api/jobs` and `GET /api/jobs/{job_id}` for polling
- added `GET /api/files/{file_id}` for file delivery
- added `GET /api/admin/stats` and `DELETE /api/admin/clear-history`
- persisted metadata in SQLite and stored files on disk
- introduced asynchronous in-process background job execution

This phase turned the prototype into a working full-stack app with durable data and file handling.

### Phase 3: Security, Deployment, and Hardening

After the core system was working, the focus shifted to making it safer and more realistic for multi-device use.

Key outcomes:

- moved runtime settings into environment-based configuration
- served the frontend from FastAPI for a single-origin deployment model
- added Caddy as an HTTPS reverse proxy
- added admin authentication with bearer tokens
- added password hashing support with PBKDF2-SHA256
- added upload validation for file size, content type, extension, and file signatures
- added per-IP rate limiting for login, upload, and job creation
- added sensitivity-based storage tiers: `low`, `medium`, `high`, and `quarantine`
- restricted access to higher-risk file tiers

This phase significantly improved the operational and security posture of the application and made the system more representative of a real deployable service.

### Phase 4: Lightweight Segmentation and Multi-User Support

The final major phase focused on image segmentation and ownership-aware access control.

Key outcomes:

- implemented a lightweight segmentation provider using SLIC superpixels and region merging
- added fallback segmentation strategies for lower-quality or low-contrast images
- generated segmentation outputs automatically on upload
- exposed segmentation artifact URLs through `GET /api/images/{image_id}/segments`
- added non-admin users and ownership-aware access control
- added deletion endpoints for user-scoped jobs and images
- stored uploads and outputs under per-user paths
- added admin user management and user login support in the frontend

This phase expanded the system from an admin-centered tool into a more complete multi-user application.

## Final System Architecture

The final system includes:

- a static multi-page frontend built with HTML, CSS, and JavaScript
- a FastAPI backend with modular route structure
- SQLite for persistent metadata
- local filesystem storage for uploads, results, and segmentation artifacts
- background jobs for asynchronous processing
- token-based authentication for admin and user access

Core frontend pages:

- `index.html` for upload and job creation
- `jobs.html` for job tracking
- `result.html` for outputs and metrics
- `admin.html` for admin stats and user management

Core backend route groups:

- `images` for uploads and segmentation discovery
- `jobs` for job lifecycle actions
- `files` for file serving
- `auth` for login and user creation
- `admin` for admin-only operations

## Key Technical Decisions

### Frontend-First Start

Beginning with a mock-driven frontend allowed the user flow to be tested before backend implementation. This reduced uncertainty and made the API contract easier to define.

### Python and FastAPI Instead of Node.js

Although an earlier idea considered Node.js for the first real backend, the project moved to Python and FastAPI because Python was a better fit for image processing and scientific-tooling expansion.

### Polling Instead of Real-Time Sockets

Polling was used for job status and admin refresh because it was simpler to build and aligned well with the staged development approach.

### Filesystem Plus SQLite

Binary files were stored on disk while metadata and lifecycle state were stored in SQLite. This kept file handling straightforward while still allowing persistent queries and admin reporting.

### Heuristic and CPU-Friendly Segmentation

Instead of depending on a heavy GPU-oriented model, the project implemented a lighter segmentation path that could run on available hardware. This was a practical tradeoff that kept the system usable in the actual project environment.

## Security and Reliability Work

The project included several layers of security and operational hardening:

- token-based authentication for admin routes
- password hashing and constant-time verification
- environment-aware startup checks for weak defaults
- upload allowlists for MIME types and extensions
- basic signature checking for supported image files
- file-size limits on uploads
- per-IP rate limiting on sensitive endpoints
- sensitivity-tiered storage and delivery rules
- ownership checks for user-specific images, jobs, and files

These additions moved the system beyond a classroom-style prototype and toward a safer application design.

## Segmentation Work

One of the most important technical additions was the automatic segmentation pipeline.

The lightweight path works by:

- generating SLIC superpixels
- merging related regions with a region adjacency graph
- scoring regions using edge strength, color difference, border difference, and region size
- selecting likely foreground regions
- applying fallback methods when needed

Fallback behavior includes:

- border-based background removal
- grayscale thresholding with connected-component cleanup
- alternate heuristics when dependencies or the primary approach are insufficient

Generated artifacts include:

- original image
- foreground image
- background image
- binary mask

This work also exposed a practical development lesson: image segmentation quality is highly dependent on the image type, so multiple fallback strategies were necessary to handle low-contrast or uniform-background cases.

## Multi-User and Admin Capabilities

The final version of the app supports both admin and regular users.

Admin capabilities:

- sign in and access protected admin routes
- view system statistics and recent jobs
- create users
- list users
- delete users and their associated data

Regular user capabilities:

- sign in from the main app workflow
- upload images
- create and track jobs
- access only their own jobs, images, and derived outputs

This ownership model made the system more realistic and demonstrated access control beyond a single-admin design.

## What the Project Demonstrates

This project shows experience with:

- frontend workflow design
- REST API development
- FastAPI and SQLModel
- authentication and authorization
- SQLite-backed persistence
- asynchronous job orchestration
- file storage design
- image-processing integration
- segmentation and fallback algorithm design
- deployment-oriented configuration and HTTPS setup
- documentation and iterative engineering improvement

## Limitations

The project is functional and well-scoped, but it still has clear future improvement areas:

- background jobs still run in-process rather than through a dedicated worker queue
- rate limiting is in-memory and process-local
- segmentation remains heuristic and would benefit from broader validation datasets
- storage is local filesystem based rather than cloud-backed
- polling is simpler than real-time push updates, but less efficient

These limitations are appropriate for the current stage and also provide clear next steps for future work.

## Lessons Learned

A few themes stand out across the project:

- starting with a prototype made later implementation decisions easier
- contract consistency between frontend and backend reduces rework
- security and deployment concerns become much more important once a project leaves localhost-only usage
- lightweight, hardware-aware solutions can be more practical than ambitious model choices
- iterative improvement was especially valuable for segmentation, where real image examples exposed weaknesses quickly

## Conclusion

Image Analysis and Segmentation Platform developed from a UI prototype into a more complete image-processing platform with backend persistence, authenticated workflows, security controls, multi-user ownership, and automatic segmentation outputs.

For a portfolio project, its strongest value is that it demonstrates end-to-end thinking: not just building pages or endpoints in isolation, but connecting interface design, backend services, data storage, access control, deployment concerns, and image-processing behavior into one coherent system.
