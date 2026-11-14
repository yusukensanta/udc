# ADR-0007: Async Runtime and Concurrency Control

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers

## Context

UDC must coordinate high-latency object-store I/O, CPU-intensive decoding/encoding, multipart uploads, and multiple independent data partitions. Async I/O can improve resource utilization, but async alone does not make a system scalable. Unbounded task creation, queues, in-flight buffers, or uploads can exhaust memory, file descriptors, sockets, and provider quotas.

## Decision drivers

1. Efficient concurrent I/O without dedicating one OS thread per request.
2. Explicit backpressure and bounded queues.
3. Independent limits for CPU work, I/O requests, memory, and multipart uploads.
4. Cancellation and graceful shutdown propagation.
5. No blocking CPU-heavy work on async worker threads.
6. Compatibility with the Rust Arrow and object-store ecosystems.

## Options considered

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Tokio** | Mature async runtime; ecosystem compatibility; bounded channels, semaphores, task scheduling | Requires disciplined task and blocking-work management; async APIs can increase complexity |
| **async-std** | Async runtime with familiar standard-library-like APIs | Ecosystem adoption and compatibility with selected data libraries must be evaluated |
| **Synchronous I/O with thread pools** | Simpler control flow; can be effective for CPU-bound or low-concurrency tasks | Thread-per-operation or oversized pools can waste resources; less natural for many remote I/O requests |
| **Custom runtime / executor** | Full control | Very high correctness and maintenance burden; unjustified for UDC |

## Proposed decision

Use **Tokio** as the initial async runtime candidate, subject to dependency compatibility validation. Require bounded concurrency and backpressure in every producer-consumer pipeline. Use dedicated bounded CPU execution facilities for CPU-heavy or blocking operations rather than running them directly on async worker threads.

## Rationale

UDC's main remote data path is I/O-heavy and benefits from overlapping network operations. Tokio has mature ecosystem integration and explicit mechanisms for bounding work. The critical architectural choice is not merely Tokio: it is that task count, queue capacity, in-flight bytes, and provider requests are explicitly limited.

## Required design constraints

- Never spawn one task per discovered object without a concurrency limit.
- Use bounded channels for batch and work-unit flow.
- Apply semaphores or equivalent admission control to per-provider requests, multipart parts, and open files.
- Bound memory by bytes, not only by number of RecordBatches; batch sizes vary.
- Separate CPU decode/encode capacity from network I/O capacity.
- Propagate cancellation to readers, writers, and child tasks.
- Define overload behavior: wait/backpressure, durable queue, or fail-fast; do not silently buffer without limit.

## Trade-offs and consequences

- Limits must be configurable and observable; a single global concurrency value is insufficient.
- Too-low limits underutilize resources; too-high limits trigger memory pressure, throttling, and retries.
- Async cancellation and partial multipart uploads require cleanup semantics.
- A runtime abstraction should not be built unless multiple runtimes become a real requirement.

## Validation plan

Stress test large numbers of small files and a small number of very large files. Measure peak resident memory, in-flight bytes, task count, open file descriptors, sockets, throughput, and tail latency under injected slow reads/writes and throttling. Verify bounded memory under backpressure and prompt cancellation.

## Revisit conditions

Revisit if selected ecosystem libraries require a different runtime or if benchmarks show Tokio imposes material overhead for target workloads.
