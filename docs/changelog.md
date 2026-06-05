# Changelog

## 0.1.3

- Added async Arrow IPC streaming through `ArrowIPCStream` and lower-level
    `IPCStreamSink` batch serialization.
- Added batch-draining helpers on `ArrowRecordContainer` for streaming and
    memory-constrained workflows: `drain_batches()`, `iter_batches()`, and
    `flush_partial()`.
- Improved streaming backpressure behavior with cooperative producer/consumer
    scheduling.
- Refactored append, materialization, and container state internals into helper
    modules while keeping the package-level public exports stable.
- Added benchmark matrix artifacts and profiling workflows for comparing memory
    tuning options.

## Earlier history

Use the repository's GitHub Releases page for published release artifacts and
tag history:

<https://github.com/ProxayFox/proxay-pylibs/releases>
