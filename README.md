# Static Evolution public backup

This repository is the public, read-only data mirror for [Static Evolution](https://staticevolution.com/). A scheduled GitHub Actions workflow exports the published subset of the production PostgreSQL database, writes deterministic `sqlite-diffable` files under `staticevolution/`, and commits only changed public data.

The export includes published Entries, Links, Quotes, Notes, tags, guides and Chapters, photo metadata, Pages, and Products. It excludes drafts, scheduled and unlisted content, users, sessions, permissions, admin and API audit data, credentials, private storage details, search vectors, and importer references. `test_export.py` enforces that boundary before each export.

## Local verification

```sh
python -m venv .venv
.venv/bin/pip install --require-hashes --requirement requirements.txt
.venv/bin/python -m unittest
DATABASE_URL=postgresql://… .venv/bin/python export.py
.venv/bin/sqlite-diffable dump staticevolution.db staticevolution --all
```

`DATABASE_URL` must point to a read-only production connection. Never commit or print it.

## Datasette

`build_database.py` rebuilds `staticevolution.db` from the committed snapshot when the container starts. Railway serves that immutable database through Datasette. Anonymous access is read-only. Private root access uses the password hash in `DATASETTE_ADMIN_PASSWORD_HASH`; the plaintext password is not stored in this repository or Railway.

This public mirror is not a complete private backup. Production recovery still depends on Railway PostgreSQL backups and private media-bucket recovery procedures.

## License

Repository source code is available under the MIT terms in `LICENSE`. Generated
files under `staticevolution/` and exported site content are excluded from that
grant and remain all rights reserved.
