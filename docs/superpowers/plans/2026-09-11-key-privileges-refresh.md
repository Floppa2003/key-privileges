# KEY Privileges Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Actions-backed public KEY privileges snapshot that ChatGPT can read through GitHub without Telegram or a desktop session.

**Architecture:** A dependency-free Node.js scraper fetches the public KEY Netlify application data, optionally overlays the production Supabase content snapshot, validates the result, and writes normalized JSON. GitHub Actions refreshes on demand through `key/trigger.json`, every six hours, and manually.

**Tech Stack:** Node.js 22+, built-in `fetch`, `node:vm`, `node:test`, GitHub Actions, GitHub Contents API.

**Spec:** `docs/superpowers/specs/2026-09-11-key-privileges-refresh-design.md`

## Global Constraints

- No Telegram credentials, browser cookies, `initData`, user sessions, or private KEY data.
- Fetch only the configured public KEY Netlify/Supabase sources.
- Do not execute the whole downloaded application; isolate and validate only required data literals.
- Do not publish a base catalog with fewer than 20 partners.
- Supabase override failure is non-fatal but must be visible as `remote_ok: false`.
- A requested refresh is verified only after `status.request_id` matches the triggering request.

---

### Task 1: Implement and test the scraper

**Files:**
- Create: `key/refresh.mjs`
- Create: `key/refresh.test.mjs`

**Interfaces:**
- Consumes: public KEY Netlify JavaScript and optional Supabase JSON.
- Produces: `key/catalog.json` and `key/status.json`.

- [ ] Write parser tests for balanced literals, executable-construct rejection, partner content IDs, Supabase config extraction, remote snapshot envelopes, and remote card overlays.
- [ ] Run `node --test key/refresh.test.mjs` and verify the tests exercise the intended parser seams.
- [ ] Implement the minimal dependency-free scraper with strict validation and atomic publish-after-validation behavior.
- [ ] Run the tests again and verify all pass.

### Task 2: Add refresh automation and consumer documentation

**Files:**
- Create: `.github/workflows/refresh-key.yml`
- Create: `key/trigger.json`
- Create: `README.md`

**Interfaces:**
- Consumes: push changes to `key/trigger.json`, cron, or `workflow_dispatch`.
- Produces: committed refreshed `key/catalog.json` / `key/status.json`.

- [ ] Add a workflow using `ubuntu-latest`, Node.js 22, `contents: write`, serialized concurrency, tests-before-refresh, and commit/push of output files.
- [ ] Add an initial trigger payload and README describing the consumer contract and freshness semantics.
- [ ] Verify the workflow file and scraper can be read back from `main` after the writes.

### Task 3: Run and verify end-to-end

**Files:**
- Modify: `key/trigger.json`
- Verify: `key/status.json`
- Verify: `key/catalog.json`

**Interfaces:**
- Consumes: a unique `request_id` in `key/trigger.json`.
- Produces: a matching successful `status.request_id` and a normalized catalog with at least 20 partners.

- [ ] Update `key/trigger.json` with a unique request ID to start a real workflow.
- [ ] Inspect the resulting Actions run/job logs; fix implementation defects if the run fails.
- [ ] Read `key/status.json` back and require `ok: true`, matching `request_id`, `partner_count >= 20`, and a non-empty content hash.
- [ ] Read representative cards from `key/catalog.json` and confirm Four Seasons and Marriott data are present.
- [ ] Report completion only after that readback verification.
