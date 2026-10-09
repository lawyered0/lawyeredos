# Security and privacy reporting

Do not disclose a vulnerability using real client data, credentials, private
configuration, personal paths, account identifiers, or confidential documents.
Use a minimal fictional reproduction and describe sensitive evidence by
category rather than copying it.

Before publication, there is no public reporting channel. Immediately before
making the repository public, enable GitHub **Private vulnerability reporting**
for `lawyered0/lawyeredos`. After publication, security reports should use the
repository's private advisory form at
`https://github.com/lawyered0/lawyeredos/security/advisories/new`; ordinary
sanitized bugs may use GitHub Issues. If private reporting is not enabled and
verified, publication must stop. No security email address or response SLA is
offered.

If a suspected issue could expose confidential material:

1. stop using the affected feature;
2. preserve local evidence privately;
3. rotate affected credentials through the relevant provider if exposure is
   independently confirmed; and
4. do not upload the evidence until the repository's private advisory route is
   available and verified.

LawyeredOS does not store connector token values in its config. Reports about
Gmail or Calendar should name only the adapter and failure class, never the
account, calendar identifier, request headers, or token.
