# Publishing a new version on Zenodo

This repository can be archived on [Zenodo](https://zenodo.org/) with a version-specific DOI.
The GitHub-Zenodo integration creates a release archive automatically, but that archive
places all files inside a single top-level directory. Zenodo also does not accept folder
uploads in the web interface.

For v1.0.6 and later, use a **hybrid deposit**:

1. Upload **standalone** at the record root: `LICENSE`, `README.md`, and
   `sbcars2026-camera-ready.pdf` (copy of `docs/sbcars2026-camera-ready.pdf`).
2. Upload the full flat replication zip from:

```bash
bash scripts/make_zenodo_flat_zip.sh <tag>
```

Example for tag `v1.0.6`:

```bash
bash scripts/make_zenodo_flat_zip.sh v1.0.6 /tmp/iso-nfr-enrichment-humaneval-v1.0.6-flat.zip
```

The zip contains the same files as the GitHub release (including `LICENSE`, `README.md`, and
`docs/sbcars2026-camera-ready.pdf` at the archive root). Standalone copies satisfy reviewers
who must access those files without opening the zip.

## Creating a new Git tag and Zenodo version

After merging changes on `main`, create an annotated Git tag (e.g. `v1.0.7`) and push it
to GitHub. If the repository is linked to Zenodo, a new draft version may appear
automatically when the GitHub release is published.

Open the Zenodo record, start from **New version**, upload the standalone files and the
flat zip as described above. Do not rely on "Import files from the previous version" if that
would reintroduce a nested GitHub archive.

When the Zenodo version is published, copy its **version DOI** (not the concept DOI that
always resolves to the latest version). Update the camera-ready paper's artifact URL to
that version DOI so citations point to the exact archive you evaluated.

## Concept DOI vs version DOI

Zenodo assigns a **concept DOI** to the record (latest version) and a separate **version
DOI** to each release. Prefer the version DOI in papers and README links when you need a
fixed, citable snapshot.
