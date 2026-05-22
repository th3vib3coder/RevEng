# Source Provenance

The plugin was designed from inspected public reverse-engineering skill and tool repositories. No third-party source code is vendored into this plugin.

## Inspected Sources

- `hackersifu/reverse-engineering-skills`, commit `5e675640e0ec94372298c57bb335ecf047360688`, MIT: evidence-first IOC extraction and static-first unpacking ideas.
- `SimoneAvogadro/android-reverse-engineering-skill`, commit `6a31ed3fa2fc96d2366e057dcf13bbf5c2bdcdaa`, Apache-2.0: Android decompile/API extraction workflow ideas.
- `Arteriogramtrombiculiasis120/claude-code-reverse-engineering`, commit `d0929746bfdbead9518e620caf77ff53acd43c0d`, MIT: architecture-first documentation and plugin-system analysis ideas.
- `meyz664K/auto-re-agent`, commit `78b489e1aeae71b85b168c91402ff8dcbfef94a7`, MIT: backend abstraction and reverser/checker parity ideas.
- `NationalSecurityAgency/ghidra`: official Ghidra project used as conceptual reference for headless and PyGhidra workflows.

## Reuse Policy

- Reuse concepts, not copied implementation.
- Keep license obligations documented.
- Prefer small deterministic scripts with tests over vendoring upstream code.
