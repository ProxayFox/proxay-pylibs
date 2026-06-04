# API Reference

The stable public API is intentionally small:

- `http_to_arrow.ArrowRecordContainer`
- `http_to_arrow.UnknownFieldPolicy`
- `http_to_arrow.MissingFieldPolicy`
- `http_to_arrow.CoercionPolicy`

The underscored modules are implementation helper modules. They are documented
for maintainers and advanced readers because this site was generated with a
comprehensive module reference, but callers should prefer the package-level
exports and `ArrowRecordContainer` methods.

!!! note "Resolved API targets"
    The generated API pages target real modules in the current package:
    `http_to_arrow`, `http_to_arrow.main`, `http_to_arrow._policies`,
    `http_to_arrow._coercion`, `http_to_arrow._schema`, and
    `http_to_arrow._encoding`.

!!! warning "Internal helper modules"
    Modules whose names begin with `_` are lower-stability implementation
    helpers. They are included for completeness, not as the recommended user
    integration surface.

## Pages

- [Package Exports](package.md)
- [Container](container.md)
- [Policies](policies.md)
- [Coercion Helpers](coercion.md)
- [Schema Helpers](schema.md)
- [Encoding Helpers](encoding.md)
