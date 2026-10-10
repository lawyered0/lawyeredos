# Update, rollback, and uninstall

LawyeredOS keeps the selected workspace, configuration, tracker, and matter
outputs separate from the extracted source package. Never treat removing a
plugin or skill as authority to delete practice data.

## Before any update

1. Close active Claude or Codex sessions for the workspace.
2. Back up `.lawyeredos/config.toml`, `.lawyeredos/data/`, and matter outputs
   required by your retention obligations.
3. Extract the new package to a new stable private folder; do not overwrite the
   prior package.
4. Preview with the same stable Python runtime that will apply the update.
5. Review the exact versioned-core path, managed skill paths, and configuration
   policy before approval.
6. Keep the prior package and versioned core until a restart and fictional
   acceptance run succeed.

## Claude update and rollback

Run `scripts/setup_wizard.py` against the existing workspace with `reuse`.
`reuse` preserves the existing configuration byte-for-byte and refuses a
missing tracker. A changed module selection requires an intentional config
replacement; that replacement is backed up before it is written.

The latest Claude setup transaction can be rolled back with:

```bash
python3 scripts/setup_wizard.py \
  --workspace /absolute/path/to/workspace --rollback
```

Use the same retained Python selected during setup. Rollback proceeds only when
every managed artifact still matches the recorded transaction. Any modified
config, tracker, launcher, or plugin causes a complete safety refusal under
`preserved_modified`; rollback does not undo legal work or arbitrary files.

## Codex update and recovery

Preview the new package with `scripts/setup_codex.py`, the exact existing
workspace, `--existing-config reuse`, and the same selected modules and mail
mode. Apply only the identical approved arguments with `--apply --yes`.

Codex setup installs a new versioned core, repoints only paths recorded in
`.lawyeredos/codex-project-discovery.json`, and retains the old core. It refuses
unmanaged skill collisions, symlinked managed directories, modified launchers,
missing configuration, and unreviewed config replacement. A failed apply
removes newly created paths and restores replaced managed links/files.

There is no general Codex rollback command. If an accepted upgrade must be
reversed, stop, preserve the workspace, and propose a reviewed migration back
to the retained core; do not hand-edit symlinks or discovery state.

## Disable without deleting data

Stop using the generated launcher and stop opening the workspace as a
LawyeredOS project. Project-local skills are not global installations. Keep
`.lawyeredos/config.toml` and `.lawyeredos/data/` until independent backup and
retention decisions are complete.

## Uninstall

There is deliberately no one-command destructive uninstaller.

1. Close active host sessions and make verified backups.
2. Review the Claude `.lawyeredos/setup-state.json` or Codex
   `.lawyeredos/codex-project-discovery.json` ownership record.
3. Remove only identified installer-managed launchers, project-skill links,
   and versioned core directories.
4. Do not remove the workspace, tracker, matter files, outputs, or backups as
   part of plugin removal.
5. Remove retained configuration or data only through the user's ordinary
   retention process after independent backup verification.

Deleting the extracted source package first can break a retained runtime or
launcher; it does not uninstall skills or remove matter data.
