# Hackathon disclosure: what existed before, what ReplayForge adds

Written on 17 September 2026, before any ReplayForge implementation work, for the Nebius x NVIDIA
Global AI Hackathon (submission deadline 30 October 2026).

## Pre-existing foundation

ReplayForge depends on **benchtrace**, an existing Apache-2.0 Python package by the same author.

| | |
|---|---|
| Repository | https://github.com/theomthakur/benchtrace |
| Version used | 0.1.1 |
| Commit | `c50b962c620e89ed1d4dc4b04813e3b1ce0fe7e9` (1 September 2026) |

benchtrace already provided, before this hackathon:

- the versioned `TraceRecord` schema and JSONL persistence;
- YAML task definitions;
- the async `Provider` interface with retries, concurrency limits and an OpenAI-compatible adapter;
- a tool-calling agent loop;
- deterministic graders (exact, regex, numeric, JSON Schema, tool call) and an LLM judge grader;
- statistics: Wilson and Clopper-Pearson pass-rate intervals, exact McNemar paired comparison;
- a dated pricing snapshot and cost-per-success analysis;
- an HTML report.

ReplayForge imports benchtrace as a dependency. It does not copy benchtrace source.

## New during the hackathon window

Everything in this repository is new work, started 17 September 2026:

- the ReplayForge application and repository;
- the Nebius Token Factory provider, model-catalog discovery and NVIDIA model validation;
- the coding-task cassette format, validator and suite digest;
- isolated coding sandboxes and the coding tool set (read, list, search, patch, run, finish);
- paired baseline-versus-candidate experiment orchestration with persistence and resumption;
- coding graders (command exit, test counts, forbidden paths, file presence, tool contracts);
- regression investigation with an evidence-linked failure taxonomy;
- cost-per-success profiling with explicit measurement labels;
- the deterministic migration policy and release decision;
- the GitHub check-run release gate;
- the REST API, persisted event stream, web application and 3D Model Lab;
- deployment, documentation and the submission.

The git history of this repository is the record of when each piece was built.
