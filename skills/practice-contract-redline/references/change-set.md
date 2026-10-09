# Change-set format

Supported operations use exact text:

```json
[
  {"type":"replace","old":"exact old text","new":"replacement","section":"7.2"},
  {"type":"delete","text":"exact text"},
  {"type":"insert_after","anchor":"exact anchor","text":" new text"},
  {"type":"add_section","after_section":"exact prior paragraph","text":"new section","new_section_number":"12A"}
]
```

Matching is case-sensitive and cannot cross a paragraph boundary. Every span
must be unique. Treat existing revisions as a separate source state; never
silently edit through or straddle another reviewer's tracked change.
