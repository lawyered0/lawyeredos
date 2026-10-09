# LawyeredOS public beta website

Static, dependency-free source for `get.lawyered.lawyer`. The versioned public
download is stored under `downloads/`; the development repository remains
private.

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
