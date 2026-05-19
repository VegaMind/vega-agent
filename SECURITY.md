# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Vega, please report it privately.

**Do not open a public issue.** Instead, email **megatron.j41@gmail.com** or open a [GitHub Security Advisory](https://github.com/VegaMind/vega-agent/security/advisories/new).

We will:
1. Acknowledge receipt within 48 hours
2. Investigate and determine scope
3. Release a fix as quickly as possible
4. Credit the reporter (if desired)

## Scope

Vega is a local-first application. Most security concerns relate to:

- Data stored in `~/.vega/`
- LLM API keys in config
- Network calls to configured API endpoints
- Third-party dependencies

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.x     | ✅ Active development |