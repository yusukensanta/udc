# ADR-0019: Packaging, Release, and Distribution

- **Status:** Proposed
- **Date:** 2026-11-15
- **Decision owners:** UDC maintainers
- **Scope:** Distribution channels, official binary targets and feature set, crate and binary naming, release pipeline and artifact provenance, upgrade communication, and the gates for source visibility and the first package release.

## 1. Context

UDC is intended to ship as a local CLI and a reusable Rust library (PRD §11.1). No ADR has owned how it reaches users. Several existing decisions interact with distribution and leave gaps:

- ADR-0011 keeps default Cargo features minimal. A prebuilt binary has to fix one feature set, so a binary and a `cargo install` build can differ unless that is decided deliberately.
- Format, storage, TLS, and state-store libraries can bring C or C++ code that is compiled at build time. Each one adds requirements to every build target.
- Crate names on crates.io are global and first-come, first-served.
- The maintainers have decided that the source becomes public once the reference configuration of the first evidence gate runs, during Phase 0, and that packages are first published at the MVP release (§12). The repository was made public on 2026-11-18, after the preconditions of §12.1 were met.

Facts established on 2026-11-15:

- The name `udc` belongs to unrelated projects on crates.io, PyPI, and npm. The crates.io and PyPI packages each install a command named `udc`, and the PyPI one is itself a data command-line tool. The full results are in §6.2.
- The thirteen crate names in the PRD's illustrative layout (`udc-core`, `udc-cli`, and the other `udc-*` names) were unclaimed on crates.io.
- crates.io prohibits publishing a crate only to reserve a name. A publish is permanent, and a published crate is its source code.
- crates.io Trusted Publishing is configured per crate and only after that crate's first, manual publish.

## 2. Decision drivers

1. A data engineer without a Rust toolchain can install UDC with one command.
2. Every channel installs the same capabilities, or the difference is explicit.
3. Users can verify where a release artifact came from.
4. CI holds no long-lived publishing secret.
5. Release work stays proportional: automated, with few channels at first.
6. The build matrix stays tractable despite native dependencies.
7. An upgrade never silently misreads persisted job state.
8. Source visibility and package publication are separate decisions, each with its own gate.

## 3. Options considered

### 3.1 Distribution channels

| Option | Strengths | Limitations / risks |
|---|---|---|
| **`cargo install` from crates.io only** | No release infrastructure; natural for Rust users | Needs a Rust toolchain and the C/C++ tools of every native dependency; compiles on the user's machine; yields default features unless flags are passed |
| **Prebuilt binaries on GitHub Releases with install scripts** | No toolchain; fast; one feature set that CI has tested | Fixes one feature set; one build per target; artifacts are reachable only from a public repository |
| **OS package managers (Homebrew, winget, apt/rpm, Nix)** | Familiar install and upgrade path | Per-ecosystem maintenance; homebrew-core requires a stable release |
| **PyPI wheel that carries the binary** | Fits Python-centric data tooling (`pip`, `uvx`) | Separate build and manylinux constraints; name availability not checked |
| **Container image** | Reproducible runtime for CI and services | Not a local CLI install; the PRD does not require a container for the MVP |

### 3.2 Release automation

| Option | Strengths | Limitations / risks |
|---|---|---|
| **`dist`** | Generates the tag-driven CI workflow, per-target archives, shell/PowerShell/Homebrew/npm/MSI installers, and attestation steps | Does not publish to crates.io; PyPI, container, and winget outputs are not available |
| **Hand-written workflows** | Full control | Every target, installer, and checksum step is maintained by hand |
| **`release-plz` or `cargo publish --workspace` for crates** | Handles version bumps, changelogs, and multi-crate publishing | Separate from binary releases; Cargo does not document a multi-crate publish as atomic |

### 3.3 Repository visibility

| Option | Strengths | Limitations / risks |
|---|---|---|
| **Private until the first MVP release** | No outside expectations before the product works; planned names stay unseen | No outside feedback before the MVP; the history to audit keeps growing |
| **Public once the reference configuration runs, during Phase 0; packages at the MVP release** | Something runnable to show, and outside comments are possible early at no cost; the history is audited while it is small | Planned crate names are visible before they can be published; issues and expectations arrive before the project can support users |
| **Public now** | Earliest feedback | Nothing runnable to show; the design will still change substantially |

## 4. Proposed decision

Distribute UDC as **prebuilt binaries plus crates.io packages**, starting at the first MVP release. The repository becomes public earlier, once the reference configuration of the first evidence gate runs, during Phase 0, as public development without packages (§12).

- **First wave:** per-target archives on GitHub Releases with shell and PowerShell installers; a project Homebrew tap; crates.io for the library crates and for `cargo install` and `cargo binstall`.
- **Second wave, on demand after the MVP:** a PyPI wheel carrying the binary, a container image, and winget. Each is added only under the rules in §9.
- **Naming:** the CLI package is `udc-cli` on every registry and it installs a command named `udc`. UDC publishes no package named `udc`. Two fallback plans are prepared in §6.3.
- **One official feature set:** every binary channel ships the same capabilities, and `cargo install udc-cli` with no flags produces the same set.
- **Automation candidates:** `dist` for binaries and installers, `release-plz` or `cargo publish --workspace` for crates, and crates.io Trusted Publishing. These are candidates to validate, not selected dependencies.

## 5. Rationale

The target users are data engineers, many of whom have no Rust toolchain. A prebuilt binary removes the toolchain and moves the cost of native dependencies from each user to the project's CI. crates.io remains necessary because the library is a product in its own right and because Rust users expect `cargo install`.

Fixing one official feature set follows the project principle that support is what has been implemented and tested. A binary whose contents depend on the channel would make the release support matrix ambiguous.

Starting with few channels keeps every channel automated. A channel that is published by hand drifts behind the others.

A package name that differs from the command it installs is established practice on crates.io: `ripgrep` installs `rg`, `fd-find` installs `fd`, and `sqlx-cli` installs `sqlx`. Publishing `udc-cli` with a `udc` command follows the same `-cli` convention and needs no special handling by `cargo install` or `cargo binstall`.

The source becomes public before the packages because the two serve different purposes. UDC is primarily a personal project, and public development costs it little: once the reference configuration of the first evidence gate runs ([PRD §13.3](../PRD.md#133-value-hypotheses-and-evidence-gates)), there is something concrete to show, and anyone who finds the project can comment in issues. Those comments are also the only evidence the PRD collects about whether others need UDC. A package, by contrast, is a promise that a user can install and rely on something, which the project cannot make before the MVP. Auditing the history for secrets is also cheapest while it holds mostly documents.

## 6. Crate and binary naming

### 6.1 Current proposal

- Every published crate uses the `udc-` prefix. The CLI package is `udc-cli` on every registry; its command is `udc`.
- Which crates are published, and how many, is owned by ADR-0011, which keeps the set small. This ADR names them and requires that the release pipeline publishes each one.
- Installation documentation always names the package `udc-cli`. It must warn that `cargo install udc` and `pip install udc` install unrelated tools.
- The `udc-` prefix is not reserved; crates.io has no namespaces. Planned names are checked again before the first package release (§12).
- UDC does not publish placeholder packages to hold names. crates.io prohibits it, and a publish cannot be undone.
- A name check on the target registry is a precondition for adding any channel.

### 6.2 Registry name check

Checked on 2026-11-15. "Free" means no package with that name was found on that date; it is not a reservation.

| Registry | `udc` | `udc-cli` | Notes |
|---|---|---|---|
| crates.io | Taken | Free | The existing `udc` crate installs a binary named `udc` |
| PyPI | Taken | Free | The existing `udc` package is a data command-line tool, last uploaded in 2023, and installs a command named `udc` |
| npm | Taken | Free | Unrelated library; no packages found under the `@udc` scope |
| Homebrew core (formula and cask) | Free | Free | The first wave uses a project tap, not homebrew-core |
| conda-forge, Chocolatey, AUR, Scoop (Main, Extras) | Free | Not checked | |
| Debian sources, nixpkgs `pkgs/by-name`, Repology | No package named `udc` | Not checked | |
| winget | No publisher starting with `udc` | Not checked | Package names under other publishers were not searched |
| Docker Hub | User and organization name `udc` free | — | |
| GitHub | Account name `udc` taken | — | Container images on GHCR would be published under the project owner's account |

### 6.3 Naming alternatives

Package names are permanent once published, and the command name spreads through documentation, examples, and the `UDC_` environment-variable prefix. The plan must therefore be fixed before CLI implementation starts in Phase 0, and cannot change after the first publish.

| Plan | Command | CLI package on every registry | Library crate prefix | Use when |
|---|---|---|---|---|
| A (current proposal) | `udc` | `udc-cli` | `udc-` | Default. The package name and the command differ, which is normal on crates.io, and two unrelated packages also install a `udc` command |
| B | `udconv` | `udconv` | `udconv-` | The mismatch or the command collision is judged unacceptable, or `udc-cli` is taken on a first-wave registry before the release |
| C | A new project name | Same as the command | The new name | The `udc-` names are taken in bulk, or the maintainers want a name that is unique and searchable |

- **Why plan A is the default:** on 2026-11-15 the two packages that install a `udc` command were barely used. The crates.io crate had 22 downloads in total and the PyPI package 38 in the preceding month, so a user having both installed is unlikely. Plan A's remaining costs appear only when PyPI becomes a channel: `uvx` assumes that the package and the command share a name, and `pip install udc` installs a different data tool.
- **Plan B** keeps the project name UDC and changes only the handle. On 2026-11-15 `udconv` was free on crates.io, PyPI, npm, and Homebrew core, and as a GitHub account name. Its advantage is that the package name equals the command on every registry, so no warning about a wrong package is needed. Its cost is a longer command and a change to every documented command and to the environment-variable prefix.
- **Plan C candidates**, free on the same five places on the same date: `omniconv`, `formatport`, `lakeferry`, `tablelift`. None is selected. A rename also changes the project name in every document.
- **Single-name fallback under plan A:** if one `udc-*` library name is taken before the first package release, choose a different suffix for that crate. If `udc-cli` is taken, or more than a few library names are, switch to plan B.

## 7. Official targets and feature set

### 7.1 Targets

First-wave targets are Rust Tier 1 platforms:

| Target | Minimum platform stated by Rust | Notes |
|---|---|---|
| `x86_64-unknown-linux-gnu` | Kernel 3.2, glibc 2.17 | UDC's own glibc floor is set by its build environment and must be chosen and recorded |
| `aarch64-unknown-linux-gnu` | Kernel 4.1, glibc 2.17 | Same glibc rule |
| `aarch64-apple-darwin` | macOS 11 | |
| `x86_64-pc-windows-msvc` | Windows 10 | |

Not in the first wave:

- `x86_64-apple-darwin`: Tier 2. Added only on demand.
- Linux musl targets: fully static binaries are attractive, but they depend on the TLS decision in §8.
- `aarch64-pc-windows-msvc`: added only on demand.

A target is supported only when the release pipeline builds it and the installation smoke test in §14 passes on it.

### 7.2 Feature set

- The official binary enables exactly the formats and storage providers in the release support matrix. For the MVP that is the capability matrix in PRD §8.2.
- `cargo install udc-cli` with no flags must produce the same feature set as the prebuilt binary. How crates and features are arranged to achieve this is owned by ADR-0011.
- Every build embeds its version, target, source commit, and compiled-in adapters, and the CLI can report them. The command that exposes this is owned by ADR-0009.
- An optional integration with a heavy native build, such as an embedded query engine, is not part of the official binary unless its owning ADR selects it for the MVP.
- Users who need a different feature set build from source. Variant binaries are not offered in the first wave.

## 8. Native dependency policy

- Every dependency that compiles C or C++ at build time is listed with its build requirements for each official target. ADR-0011 already requires this documentation; this ADR makes it a release gate.
- Official binaries link native libraries statically from vendored source where the library supports it. They must not depend at run time on a shared library other than the platform's C library and system frameworks.
- **TLS:** the default rustls crypto backend, aws-lc-rs, needs a C compiler on every platform and uses NASM on Windows when it is present. A static musl link failure with it was reported in April 2026. The TLS backend must therefore be chosen explicitly and built on every official target before that target is declared supported. Using `ring` instead is the documented alternative.
- **SQLite**, if ADR-0013 selects it: the `bundled` feature of `rusqlite` compiles SQLite from embedded source and needs only a C compiler.
- **DuckDB**, if ADR-0004 selects it: its `bundled` feature compiles C++ from source, and upstream describes cross-compilation as best-effort. It would be built natively on each target, not cross-compiled.

## 9. Channels

A channel is supported only if the release pipeline publishes to it. No channel is updated by hand.

| Channel | Wave | How users install | Requirement |
|---|---|---|---|
| GitHub Releases | First | Shell or PowerShell installer, or a direct archive download | Archives per target, checksums, and attestations |
| Homebrew tap | First | `brew install` from the project tap | Formula generated by the release pipeline |
| crates.io | First | `cargo install udc-cli`, `cargo binstall udc-cli`, or a library dependency | Release archives named so that `cargo binstall` finds them |
| PyPI wheel | Second | `pip install` or `uvx` | Name check; separate automated build |
| Container image | Second | `docker run` | Name and registry decision; automated build |
| winget | Second | `winget install` | Name check; automated manifest |

Adding a channel requires a name check on that registry, an automated publish step, and an entry in the installation smoke test.

## 10. Release pipeline and artifact provenance

- A release is produced only by CI from a version tag. No published artifact is built on a developer machine.
- **crates.io:** after the mandatory first manual publish of each crate, configure Trusted Publishing for it and enable Trusted-Publishing-only mode. CI then holds no long-lived crates.io token.
- **Every dependency is published:** crates.io rejects a crate with a path-only dependency, so each workspace crate that `udc-cli` depends on is published too, each with its own first manual publish and Trusted Publishing configuration.
- **Packaging checks on every pull request:** `cargo publish --dry-run` and `cargo package --list` for each crate, to catch missing metadata, files that should not ship, and the 10 MB crate size limit. A publish is permanent, and yanking a version does not remove its contents.
- **Required crate metadata:** `license`, `description`, `repository`, and `readme`.
- **Multi-crate publish:** treat it as non-atomic. The release procedure must be safe to re-run after a partial publish, and binaries are released only after every crate of that version is published.
- **Provenance:** every release archive carries a checksum and a GitHub artifact attestation, and the installation documentation explains how to verify it.
- All workspace crates share one version until ADR-0011's revisit condition for independent release cycles is met.

## 11. Upgrade and compatibility communication

- The compatibility surfaces of a release are the CLI and configuration schema (ADR-0009), the persisted manifest schema (ADR-0013 §14), SplitDescriptor versions (ADR-0014 §8), and error codes (ADR-0008).
- The release notes state, for each release, whether jobs persisted by the previous release can be recovered and resumed. A release that cannot read the previous manifest version is a breaking release.
- UDC has no self-update mechanism in the first wave. An upgrade uses the same channel as the installation.

## 12. Visibility and release gates

Making the source public and publishing packages are separate steps with separate gates.

### 12.1 Source visibility

The repository becomes public once the reference configuration of the first evidence gate runs, during Phase 0 (PRD §12), as **public development**:

- Interfaces are not stable. The CLI, the configuration format, the library API, and persisted formats may change without notice or migration.
- No package or binary is published, and no installation channel exists.
- There is no support commitment. Issues and discussion are welcome; a response is not guaranteed.
- The ADRs and the PRD are proposals until their status says otherwise.

Before the repository becomes public, all of the following must be true:

1. The LICENSE file is present, and the license review of every dependency used so far is complete.
2. The full git history has been audited for secrets and private data, because the history becomes public with the repository. A secret-scanning check on pull requests does not replace this audit.
3. A security policy states how to report a vulnerability privately.
4. The README states the project status and what public development means.
5. CI workflows use no secrets on pull requests and grant the workflow token read-only permissions by default.

### 12.2 First package release

Packages and binaries are first published at the MVP release. Nothing is published to crates.io, and no binary release is created, before it.

- The release pipeline is rehearsed without publishing: builds for every official target, `cargo publish --dry-run`, and installers tested against artifacts attached to a draft release, which only maintainers can see.
- Planned crate names are visible in the public repository from that point, but cannot be held before the first publish. They may be taken in the meantime; this risk is accepted, and the fallback in §6.3 applies.

Before the first package release, all of the following must be true:

1. Every planned package name has been re-checked on each first-wave registry, and the fallback in §6.3 applied to any that was taken.
2. The release support matrix, the official feature set, and the installation documentation agree.
3. The rehearsal of the release pipeline has passed for every official target.
4. The license review covers every dependency of the release.

On the release day the order is: perform the first manual publish of each crate, configure Trusted Publishing, then publish the binary release.

## 13. Trade-offs and consequences

- One official feature set means that a user who needs another adapter must build from source.
- Not owning the `udc` name on crates.io, PyPI, and npm is a lasting source of confusion that documentation has to manage. A user who guesses the package name from the command installs someone else's software.
- Each additional target adds CI time, and each native dependency multiplies it.
- Packages wait for the MVP release, so there is no outside feedback on packaging before then. The source is public earlier, so the design can be discussed.
- A public repository without packages still attracts issues and expectations. The README states what public development means.
- The first release requires manual publishing of every crate, because Trusted Publishing cannot be configured earlier.

## 14. Validation plan

- For each release and each official target: install through every supported channel in a clean environment, run the version report, run a local Parquet-to-Parquet conversion, and verify the artifact attestation.
- Confirm that `cargo install udc-cli` with no flags and the prebuilt binary report the same compiled-in adapters.
- Run the Linux binaries on the oldest distribution that the recorded glibc floor claims to support.
- Rehearse a complete release without publishing it, using a draft release, including a deliberately interrupted multi-crate publish that is then re-run.
- Create a job with the previous release, upgrade, and confirm that the job is recovered or rejected with an explicit compatibility error.

## 15. Ownership boundary

**Owns:** distribution channels, official targets, what the official binary contains, crate and binary naming, release pipeline requirements, artifact provenance, upgrade communication, and the gates for source visibility and the first package release.

**Does not own:**
- Which crates are published and how many, how crates and Cargo features are arranged to produce the official feature set, and dependency review rules — ADR-0011.
- The command and output format that report version and compiled-in adapters — ADR-0009.
- Persisted manifest versioning and migration — ADR-0013. SplitDescriptor versioning — ADR-0014.
- Which library is selected for a concern, including its native dependencies — the ADR for that concern, for example ADR-0004, ADR-0005, and ADR-0013.
- The implementation language and toolchain — ADR-0002.
- Packaging of a future self-hosted service. No ADR owns it yet; it is a future consideration in the PRD.

## 16. Revisit conditions

Revisit when the first MVP release is being prepared, when a second-wave channel is requested, when a variant binary with a different feature set is needed, or if the `udc` crate name becomes available.

## 17. References

- Registry lookups on 2026-11-15: the crates.io, PyPI, npm, Homebrew, conda-forge, Chocolatey, AUR, Debian sources, Repology, Docker Hub, and GitHub APIs
- [crates.io policy update (RFC 3463)](https://rust-lang.github.io/rfcs/3463-crates-io-policy-update.html)
- [crates.io Trusted Publishing (RFC 3691)](https://rust-lang.github.io/rfcs/3691-trusted-publishing-cratesio.html)
- [crates.io development update, January 2026](https://blog.rust-lang.org/2026/01/21/crates-io-development-update)
- [Cargo: specifying dependencies](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html)
- [Cargo: publishing on crates.io](https://doc.rust-lang.org/cargo/reference/publishing.html)
- [cargo publish](https://doc.rust-lang.org/cargo/commands/cargo-publish.html)
- [Rust platform support](https://doc.rust-lang.org/nightly/rustc/platform-support.html)
- [dist installers](https://axodotdev.github.io/cargo-dist/book/installers/index.html)
- [dist configuration reference](https://axodotdev.github.io/cargo-dist/book/reference/config.html)
- [cargo-binstall support](https://github.com/cargo-bins/cargo-binstall/blob/v1.4.9/SUPPORT.md)
- [release-plz](https://release-plz.dev/docs)
- [maturin bindings](https://maturin.rs/bindings)
- [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- [aws-lc-rs Windows requirements](https://aws.github.io/aws-lc-rs/requirements/windows.html)
- [Static musl link failure report, April 2026](https://lists.reproducible-builds.org/pipermail/rb-general/2026-April/004086.html)
- [rusqlite](https://github.com/rusqlite/rusqlite)
- [duckdb-rs](https://github.com/duckdb/duckdb-rs)
- [Homebrew acceptable formulae](https://docs.brew.sh/Acceptable-Formulae)

## 18. Related ADRs

- [ADR-0002: Rust as the Implementation Language](ADR-0002-rust-implementation-language.md)
- [ADR-0004: Execution Engine Selection](ADR-0004-execution-engine-selection.md)
- [ADR-0005: Storage Abstraction](ADR-0005-storage-abstraction.md)
- [ADR-0008: Error Handling, Retry, and Failure Boundaries](ADR-0008-error-handling-and-retry.md)
- [ADR-0009: CLI and Job Configuration](ADR-0009-cli-and-configuration.md)
- [ADR-0011: Dependency and Feature Management](ADR-0011-dependency-and-feature-management.md)
- [ADR-0013: Job Manifest and State Management](ADR-0013-job-manifest-and-state-management.md)
- [ADR-0014: File Format Adapter Contract](ADR-0014-file-format-adapter-contract.md)
