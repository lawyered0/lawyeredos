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
