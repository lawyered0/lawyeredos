# Historical website snapshot

This directory is retained as release history. The current public page and
reviewed host-specific downloads are maintained in
[`lawyered0/lawyered0.github.io`](https://github.com/lawyered0/lawyered0.github.io)
and at <https://www.lawyered.lawyer/lawyeredos>.

Do not deploy this snapshot or treat its bundled beta.1 archive as the current
download. Source contributions belong in `lawyered0/lawyeredos`; publishing a
source change does not replace a reviewed release ZIP.

## Local preview

Run the server from this directory so the versioned download resolves:

```bash
python3 -m http.server 4173 \
  --directory /absolute/path/to/website
```

Then open:

```text
http://127.0.0.1:4173/
```

The page has no build step, external assets, analytics, network forms, service
workers, or third-party scripts. Deploy the HTML, CSS, JavaScript, image, and
versioned ZIP together.

## Release update checklist

- add the newly reviewed versioned ZIP under `downloads/`;
- update the version, SHA-256, release notes, and tested limits together;
- re-run privacy, responsive, accessibility, download, and link checks; and
- publish only the exact reviewed site and archive.
