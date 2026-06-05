# API Reference

The stable public API is intentionally small:

- `http_to_arrow.ArrowRecordContainer`
- `http_to_arrow.ArrowIPCStream`
- `http_to_arrow.IPCStreamSink`
- `http_to_arrow.UnknownFieldPolicy`
- `http_to_arrow.MissingFieldPolicy`
- `http_to_arrow.CoercionPolicy`

The underscored modules are implementation helper modules. They are documented
for maintainers and advanced readers because this site was generated with a
comprehensive module reference, but callers should prefer the package-level
exports and `ArrowRecordContainer` methods.

!!! note "Reference coverage"
    The generated API pages cover the package exports, container, streaming
    helpers, policies, coercion helpers, schema helpers, and encoding helpers.
    Internal helper modules may move as the implementation is split or merged;
    callers should treat the package exports and documented class methods as the
    supported integration surface.

!!! warning "Internal helper modules"
    Modules whose names begin with `_` are lower-stability implementation
    helpers. They are included for completeness, not as the recommended user
    integration surface.

## Pages

- [Package Exports](package.md)
- [Container](container.md)
- [Streaming](streaming.md)
- [Policies](policies.md)
- [Coercion Helpers](coercion.md)
- [Schema Helpers](schema.md)
- [Encoding Helpers](encoding.md)
