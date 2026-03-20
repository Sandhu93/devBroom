# Security Policy

## Supported Versions

Only the latest release receives security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Scope

devBroom is a local disk-cleanup tool with no network surface, no authentication, and no server component. Security issues relevant to this project include:

- **Unintended file deletion** — logic that could cause files or directories outside the intended scan root to be deleted
- **Symlink traversal** — following symlinks in a way that deletes data outside the scanned directory
- **Path traversal via settings** — a malformed `~/.devbroom.json` causing deletions in unexpected locations
- **Marker-file spoofing** — crafted `pyvenv.cfg` or directory structures that trick the scanner into misidentifying targets

Reports about general Python or OS behaviour that devBroom cannot control are out of scope.

## Reporting a Vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use [GitHub private vulnerability reporting](https://github.com/Sandhu93/devBroom/security/advisories/new) to submit a report confidentially. You will need a GitHub account.

Include as much of the following as possible:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- The version of devBroom affected
- Your operating system and Python version

## Response Timeline

| Milestone | Target |
| --------- | ------ |
| Acknowledgement | Within 5 business days |
| Initial assessment | Within 10 business days |
| Fix or mitigation | Dependent on severity and complexity |

You will be kept informed at each stage. If a vulnerability is confirmed, a fix will be released and you will be credited in the release notes unless you prefer to remain anonymous.

If a report is declined, a reason will be provided.
