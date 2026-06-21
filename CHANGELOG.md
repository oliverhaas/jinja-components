# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0a1] - 2026-06-19

First alpha release.

### Added

- `Component` base class; subclasses register under their class name and pair
  with a co-located template.
- Compile-time rewriting of `<PascalCase>` tags into `component()` calls during
  Jinja2's `preprocess` step, so rendering stays on the bytecode-cached path.
- Slots aligned with native Web Components: a default slot, named slots filled
  with the `slot` attribute (or `<template slot="name">`), and `<slot>` fallbacks.
- `register` for aliasing a component under additional names.
- Template resolution from a component's package, configurable via `setup(package=...)`.
- Django Jinja2 backend integration through `jinja_components.django.environment`
  and the `JINJA_COMPONENTS` setting.

[Unreleased]: https://github.com/oliverhaas/jinja-components/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/oliverhaas/jinja-components/releases/tag/v0.1.0a1
