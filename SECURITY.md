# Security and privacy reporting

Use GitHub's private vulnerability-reporting form:

<https://github.com/lawyered0/lawyeredos/security/advisories/new>

The repository must not invite public contributions until the **Report a
vulnerability** control is enabled and verified. If that control is not
available, do not open a public issue containing security details; wait for the
private route to be restored.

Do not disclose a vulnerability using real client data, credentials, private
configuration, personal paths, account identifiers, or confidential documents.
Use a minimal fictional reproduction and describe sensitive evidence by
category rather than copying it. No response-time commitment is made.

If a suspected issue could expose confidential material:

1. stop using the affected feature;
2. preserve local evidence privately;
3. rotate affected credentials through the relevant provider if exposure is
   independently confirmed; and
4. submit only a minimal fictional or fully sanitized reproduction through the
   private advisory route.

LawyeredOS does not store connector token values in its config. Reports about
Gmail, Calendar, or session tools should name only the host, adapter, and
failure class—never the account, calendar identifier, request headers, or
token.

## Local installer boundary

Setup and rollback reject symlink substitutions, unexpected post-preview
artifacts, paths outside their exact project-local namespaces, and managed
artifacts whose recorded fingerprints have changed. These checks are
path-based: the current implementation does not hold parent directory file
descriptors and perform every mutation with `openat`-style operations. A local
process able to rewrite the workspace concurrently could therefore race a
successful check. Do not run setup or rollback while another process is
modifying `.lawyeredos`, `.claude`, or `.agents`; stop and rerun the preview if
the workspace changes.

New confidential app-owned paths use `0700` directories and `0600` files.
Existing modes are never silently broadened or tightened: an unsafe existing
path produces a migration-required error and remains byte-for-byte and
mode-for-mode unchanged. See `docs/MIGRATION.md`. This policy deliberately does
not apply recursive permission changes to user workspaces or matter folders.
