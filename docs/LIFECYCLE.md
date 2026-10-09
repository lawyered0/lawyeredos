# Update, rollback, and uninstall

## Update

1. Back up the workspace's `.lawyeredos/config.toml` and `data/` directory.
2. Extract the new release to a new stable private folder.
3. Preview with a stable Python 3.11+ runtime. Create `.venv` and install the
   approved pinned requirements only when the selected modules need them.
4. Run its wizard against the existing workspace with `reuse`.
5. Review the proposed versioned plugin and launcher path before applying.
6. Run the fictional first-matter acceptance flow before using client data.
7. Keep the previous extracted package, runtime, and versioned plugin until the
   new version has been accepted and a restart succeeds.

`reuse` preserves existing configuration byte-for-byte and refuses a missing
tracker. A changed module selection requires an intentional config replacement;
that replacement is backed up first.

## Roll back the latest setup transaction

Run `scripts/setup_wizard.py --workspace /absolute/path/to/workspace
--rollback` with the same retained Python used for setup (`python3` or
`.venv/bin/python`).

Rollback proceeds only when every managed artifact still matches the state
recorded at apply time. If config, tracker, launcher, or plugin content changed,
the entire rollback is refused and the drift is listed under
`preserved_modified`. Rollback does not undo legal work, delete outputs, or
revert arbitrary workspace files.

The values in `managed_fingerprints` are typed ownership fingerprints, not raw
file SHA-256 values. For a regular file the wizard hashes the `file\0` type tag
followed by the file bytes. Compare them only by using the wizard's fingerprint
algorithm; a raw `shasum` value will intentionally differ.

## Disable without deleting data

Stop launching through `launch-lawyeredos.sh`. The project-local plugin is not a
global Claude installation, so no global plugin entry needs removal. Keep the
workspace's `.lawyeredos/data/` and config until retention and backup decisions
are complete.

## Uninstall

There is deliberately no one-command destructive uninstaller.

1. Close active Claude Code sessions for the workspace.
2. Back up `.lawyeredos/config.toml`, `.lawyeredos/data/`, and any matter
   outputs required by your retention obligations.
3. Review `.lawyeredos/setup-state.json` and the paths under
   `.lawyeredos/plugins/`.
4. Remove only the generated launcher and versioned plugin directories you have
   identified. Do not delete the workspace or `.lawyeredos/data/` as part of a
   plugin uninstall.
5. Remove config, tracker data, scratch, and backups only through the firm's
   ordinary retention process and only after independent backup verification.

Deleting the retained extracted package first will break its launcher but will
not remove matter data.
