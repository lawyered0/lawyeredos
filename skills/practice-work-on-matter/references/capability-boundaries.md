# Capability boundaries

- **Mail:** setup records one of three states: unavailable by explicit skip;
  Claude Gmail connector configured but not locally verifiable; or experimental
  local `gmail.readonly` REST adapter. Only a successful bounded read in the
  active session establishes a connection for that request. Preserve ambiguity
  and never draft, send, reply, forward, label, archive, or delete from the
  matter-orientation workflow.
  An ordinary orientation runs the bounded matter-mail plan. Session tools are
  used only when actually present and authorized. Missing bodies, attachment
  bytes, pages, or supported extraction keep the local complete checkpoint from
  advancing. No route polls in the background or changes Gmail state.
- **Calendar:** orientation may inspect or propose; it may not create, update,
  or delete events.
- **Practice manager:** unavailable by default. Never treat a tracker write as
  authorization for an external account write.
- **PDF/OCR:** use `${LAWYEREDOS_ROOT}/scripts/extract_pdf.py` for local text
  extraction. `review` means the extraction is too sparse for reliance. No OCR
  engine is bundled in this first version; stop dependent work or use an audited
  configured OCR route. Images do not prove a signature or missing text.
- **Jurisdiction:** `none` means no jurisdiction-specific legal computation.
  An installed profile supplies boundaries and sources, not automatic legal
  authority.
