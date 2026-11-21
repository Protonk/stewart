# Linux development

The development checkout is `/home/stewart-dev/stewart` in the Lima guest
`stewart`. Two steps require the maintainer's own login.

- [ ] From a private development-user terminal, unlock the Secret Service
  collection and enter a GitHub HTTPS credential scoped to
  `Protonk/stewart`. Confirm keyring storage, configure Git and verify
  `git push --dry-run origin HEAD:main` from the guest checkout.
  [Guest Git setup](apparatus/lima/README.md#git-transport)
- [ ] Sign in to the installed, signature-verified Linux arm64 Claude Code
  executable from the development-user terminal. Use the dedicated guest
  configuration directory and open the sign-in URL on the Mac. Record the
  maintainer's confirmation. The offline rehearsals cover the synthetic peer.
  A real model or harness probe requires its own bounded authority.
  [Maintainer sign-in](apparatus/claude-code/README.md#maintainer-sign-in)

The Mac holds the source copies of selected original encounters and
independent witnesses because the guest disk shares its physical storage.
Keep those copies until an independent backup exists at an authorized
destination. Reviewed results and their retention conditions are in the
[qualification record](apparatus/qualified.md).

After both login checks, remove this plan and its row in the
[release work order](RELEASE-PLAN.md#work-order).
