# Security Policy

## Supported versions

UDC has no release. Nothing is published to crates.io or any other package registry, and no binary is distributed (ADR-0019). The only code that receives security fixes is the `main` branch.

## Reporting a vulnerability

Report a vulnerability privately through GitHub's private vulnerability reporting:

1. Open the repository's **Security** tab.
2. Select **Report a vulnerability**.

Or go directly to <https://github.com/yusukensanta/udc/security/advisories/new>.

Do not report a vulnerability in a public issue, pull request, or discussion.

Include what you can of the following:

- The affected file, workflow, or component, and the commit you looked at.
- What an attacker can do, and under what conditions.
- Steps to reproduce, or a proof of concept that does not touch systems you do not own.

## What to expect

UDC is primarily a personal project maintained by one person, and it carries no support commitment. A response time is therefore not guaranteed. A report is acknowledged when it is read, the fix is prepared in a private security advisory, and the advisory is published once the fix is on `main`. Reporters are credited in the advisory unless they ask not to be.

## Scope

In scope:

- Code, scripts, and documentation in this repository.
- The GitHub Actions workflows under `.github/workflows`, including their permissions and their handling of pull requests.

Out of scope:

- Vulnerabilities in a dependency. Report those to the dependency's maintainers; a report here is still welcome when UDC's use of the dependency makes the problem worse.
- The fixed access keys in `tools/s3/compose.yml` and the workflows that use it. They configure a disposable local S3 container and grant access to nothing else.
- The unrelated packages named `udc` on crates.io, PyPI, and npm.
