# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.0-alpha | :white_check_mark: |

EnerGIS is a research framework. Security patches are applied to the
latest release on a best-effort basis.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Send a description of the vulnerability by email to:

**lukas.ruess@eep.uni-stuttgart.de**

Include the following in your report:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Affected version(s)
- Any suggested mitigation if known

You will receive an acknowledgement within **5 business days**.
We aim to release a fix or mitigation within **30 days** for confirmed issues.

## Scope

EnerGIS is an offline optimization tool and does not expose network services,
accept external connections, or process untrusted user input in a web context.
The primary attack surface is:

- **YAML/JSON config files**: parsed via PyYAML (safe_load) and json
- **Excel input data**: parsed via openpyxl
- **Solver communication**: local subprocess calls to GLPK/Gurobi/CBC

If you discover a vulnerability in a dependency, please also report it
upstream to the relevant project.
