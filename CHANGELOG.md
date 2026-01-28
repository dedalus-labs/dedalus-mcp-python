# Changelog

## [0.7.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.6.0...v0.7.0) (2026-01-28)


### Features

* **connection:** make name optional for single-connection servers ([7ee84b8](https://github.com/dedalus-labs/dedalus-mcp-python/commit/7ee84b8ce8842e49a5ad2cbcb800c21f822f0442))
* **dispatch:** use structured errors for connection resolution ([b0fc7b4](https://github.com/dedalus-labs/dedalus-mcp-python/commit/b0fc7b4423935f52f1f2450bd93567ea921f070b))
* **exceptions:** add ToolErrorCode enum and ConnectionResolutionError ([6f8043e](https://github.com/dedalus-labs/dedalus-mcp-python/commit/6f8043e4ae3bb46fd9ad801ed1c6e4d83e436765))
* **testing:** add ConnectionTester for local debugging ([6da1bea](https://github.com/dedalus-labs/dedalus-mcp-python/commit/6da1bea97a05cc265c209f5a764c8d22fb51057e))
* **testing:** add ToolError and mock_context utilities ([699abca](https://github.com/dedalus-labs/dedalus-mcp-python/commit/699abcab69e1672c13fc77c7cda6b31e488e4d43))
* **tools:** catch ToolError and format for LLM ([3c443ae](https://github.com/dedalus-labs/dedalus-mcp-python/commit/3c443aeeeae83b0c7fceecade7aac7e3dc3cd59c))

## [0.6.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.5.0...v0.6.0) (2026-01-20)


### Features

* **server:** add ServerConfig for centralized parameterization ([07ae1c5](https://github.com/dedalus-labs/dedalus-mcp-python/commit/07ae1c52b8aaa4ebe04ccdda6fed0f9362513934))


### Bug Fixes

* ergonomic papercuts ([0d22064](https://github.com/dedalus-labs/dedalus-mcp-python/commit/0d22064bdb3bc00ea520639eaf32e732c04cf464))


### Documentation

* **api:** add doctest examples to core classes and decorators ([a45fdf9](https://github.com/dedalus-labs/dedalus-mcp-python/commit/a45fdf935f6684178988067fecbc29f2d61b89a9))
* **auth:** rewrite connectors.md for Connection/SecretKeys API ([ca6de8b](https://github.com/dedalus-labs/dedalus-mcp-python/commit/ca6de8b30a81cc1ef25370c96428469aa7130995))
* **style:** add enum preference guideline ([1ba5f87](https://github.com/dedalus-labs/dedalus-mcp-python/commit/1ba5f8746bf5e9a75ccecf862b896f5b1e39450b))

## [0.5.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.4.1...v0.5.0) (2025-12-18)


### Features

* auth flow for client ([4b5540d](https://github.com/dedalus-labs/dedalus-mcp-python/commit/4b5540de43d59ec62f282853332f45b2e0f66ecd))


### Bug Fixes

* update reference mcp version ([47064ed](https://github.com/dedalus-labs/dedalus-mcp-python/commit/47064ed36ae586f3b30ce381c7bf0d0488504c2b))
* update reference mcp version ([#52](https://github.com/dedalus-labs/dedalus-mcp-python/issues/52)) ([7b7bcda](https://github.com/dedalus-labs/dedalus-mcp-python/commit/7b7bcda867cb612ade8bfb5dd895170d41b35f64))

## [0.4.1](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.4.0...v0.4.1) (2025-12-17)


### Bug Fixes

* improve error handling ([4c92707](https://github.com/dedalus-labs/dedalus-mcp-python/commit/4c9270743bbae81c06bb2944be6433274c400c92))
* improve error handling ([#47](https://github.com/dedalus-labs/dedalus-mcp-python/issues/47)) ([ecc018b](https://github.com/dedalus-labs/dedalus-mcp-python/commit/ecc018bbe156054ec400b8a354e828c96692ec19))

## [0.4.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.3.0...v0.4.0) (2025-12-17)


### Features

* url encoding ([6d00f4a](https://github.com/dedalus-labs/dedalus-mcp-python/commit/6d00f4a04b2ee53f06ee13075dcd6e7bbbdabd14))
* url encoding ([#44](https://github.com/dedalus-labs/dedalus-mcp-python/issues/44)) ([39bc3ca](https://github.com/dedalus-labs/dedalus-mcp-python/commit/39bc3ca6638bd0ce56826d224dc5c25605a91d89))

## [0.3.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.10...v0.3.0) (2025-12-17)


### Features

* auth server ([ad02b90](https://github.com/dedalus-labs/dedalus-mcp-python/commit/ad02b905f972e57fc9a404e437bd8bc1280bd689))
* auth server ([#41](https://github.com/dedalus-labs/dedalus-mcp-python/issues/41)) ([0937148](https://github.com/dedalus-labs/dedalus-mcp-python/commit/0937148d2cf6a11d0936aaa981a6c14152fb5af7))

## [0.2.10](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.9...v0.2.10) (2025-12-17)


### Bug Fixes

* enable auth ([cf92543](https://github.com/dedalus-labs/dedalus-mcp-python/commit/cf925435243cf7a36c97f2bb991b521dd88ef3e2))
* enable auth ([#38](https://github.com/dedalus-labs/dedalus-mcp-python/issues/38)) ([6b7edf0](https://github.com/dedalus-labs/dedalus-mcp-python/commit/6b7edf0fd42d773eb502520b2c726ee36ab12d7b))

## [0.2.9](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.8...v0.2.9) (2025-12-17)


### Bug Fixes

* connections ([830e2f6](https://github.com/dedalus-labs/dedalus-mcp-python/commit/830e2f674950bd7d8194d1fbd174f52a8d360a96))
* connections ([#35](https://github.com/dedalus-labs/dedalus-mcp-python/issues/35)) ([1cfe635](https://github.com/dedalus-labs/dedalus-mcp-python/commit/1cfe6356c7ed7cf1550d85622fcdb7be6d276ef5))

## [0.2.8](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.7...v0.2.8) (2025-12-16)


### Bug Fixes

* required changes ([82c5a72](https://github.com/dedalus-labs/dedalus-mcp-python/commit/82c5a72766f56ec3a22d7c292c7e4815dd37731b))
* required changes ([#32](https://github.com/dedalus-labs/dedalus-mcp-python/issues/32)) ([8c20723](https://github.com/dedalus-labs/dedalus-mcp-python/commit/8c2072336d6d6147570d567d2a402b83936d25ba))

## [0.2.7](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.6...v0.2.7) (2025-12-16)


### Bug Fixes

* typed Connections schema ([8f46863](https://github.com/dedalus-labs/dedalus-mcp-python/commit/8f468632c68fc3aa3e1f992da493ccf2349ee8b2))
* typed Connections schema ([ed28a0e](https://github.com/dedalus-labs/dedalus-mcp-python/commit/ed28a0eb04e805343af30a43d49ce5f7b193733f))

## [0.2.6](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.5...v0.2.6) (2025-12-11)


### Bug Fixes

* dispatch double slug error ([6a21d3c](https://github.com/dedalus-labs/dedalus-mcp-python/commit/6a21d3c39e7182fe5c665c25e0d013a98f0a25f6))

## [0.2.5](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.4...v0.2.5) (2025-12-11)


### Bug Fixes

* headers parsing ([800dabc](https://github.com/dedalus-labs/dedalus-mcp-python/commit/800dabc764109014580e1d3359f7ce4ca6d8b8d3))
* headers parsing ([08d7cf0](https://github.com/dedalus-labs/dedalus-mcp-python/commit/08d7cf065189dc8a7be59f402d45b2b72e5b0bc1))

## [0.2.4](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.3...v0.2.4) (2025-12-10)


### Bug Fixes

* exported parameter settings ([41324ed](https://github.com/dedalus-labs/dedalus-mcp-python/commit/41324ed02bd2bdda46143e3b7f6ed621aa7a5e06))
* exported parameter settings ([01e5c5f](https://github.com/dedalus-labs/dedalus-mcp-python/commit/01e5c5f3ceeae48751b39bc9379817ee930d002c))

## [0.2.3](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.2...v0.2.3) (2025-12-10)


### Bug Fixes

* port ([1974d73](https://github.com/dedalus-labs/dedalus-mcp-python/commit/1974d73d4796c3c45114f71c8304c03bbd94cf9c))
* port ([7878f43](https://github.com/dedalus-labs/dedalus-mcp-python/commit/7878f435f29576e7bb45fb4d60801707720759ce))

## [0.2.2](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.1...v0.2.2) (2025-12-10)


### Bug Fixes

* more permissive security settings ([66fe39f](https://github.com/dedalus-labs/dedalus-mcp-python/commit/66fe39f06f82a93315683dec970b5ad8d36b982d))
* more permissive security settings ([f533b56](https://github.com/dedalus-labs/dedalus-mcp-python/commit/f533b56da9c083f2621d8333c514aa091cdb1cd5))

## [0.2.1](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.2.0...v0.2.1) (2025-12-09)


### Bug Fixes

* lint warning ([14bb8d9](https://github.com/dedalus-labs/dedalus-mcp-python/commit/14bb8d9e8872937cca97ab88629c2294210630d4))
* lint warning ([d3768f7](https://github.com/dedalus-labs/dedalus-mcp-python/commit/d3768f7b5c9f82adaa100adeca95f08defd9d621))

## [0.2.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.1.0...v0.2.0) (2025-12-04)


### Features

* nov 30 changes ([5da68a0](https://github.com/dedalus-labs/dedalus-mcp-python/commit/5da68a06b01c96d672c4fe245a849abd03d67eb6))

## [0.1.0](https://github.com/dedalus-labs/dedalus-mcp-python/compare/v0.0.1...v0.1.0) (2025-12-04)


### Features

* nov 30 changes ([5da68a0](https://github.com/dedalus-labs/dedalus-mcp-python/commit/5da68a06b01c96d672c4fe245a849abd03d67eb6))

## Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This changelog is automatically maintained by [release-please](https://github.com/googleapis/release-please).
