# Capability boundaries

- **Mail:** no live adapter is bundled. Use a verified Claude connector only
  when installed and authorized. Search a bounded scope, preserve ambiguity,
  and do not change mailbox state unless separately requested.
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
