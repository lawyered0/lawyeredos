# LawyeredOS website preview

Static, dependency-free preview for a possible future `get.lawyered.lawyer`
project site. This folder is intentionally separate from the LawyeredOS
distribution package.

## Local preview

Run the server from the parent task directory so the explicitly private local
archive link resolves without copying the ZIP into the website:

```bash
python3 -m http.server 4173 \
  --directory /absolute/path/to/the/task-directory
```

Then open:

```text
http://127.0.0.1:4173/lawyeredos-site-preview/
```

The page has no build step, external assets, analytics, network forms, service
workers, or third-party scripts. Deploy `index.html`, `styles.css`, `script.js`,
and `wizard-terminal.png` together on any static host after removing or
replacing the local archive link. Do not deploy the parent directory.

## Before publication

- choose the public repository, publisher identity, support route, and download
  destination;
- decide whether the local archive call-to-action should become a public
  download, source link, waitlist, or documentation link;
- complete name/trademark review and final copy/legal review;
- re-run responsive, accessibility, and link checks on the intended host; and
- remove all private-preview language only when the release is actually public.
