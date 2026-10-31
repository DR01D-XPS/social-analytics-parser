# Social Analytics Parser

A local social-analytics dashboard with a VK connector, charts and CSV export.

`python` `fastapi` `sqlite` `analytics`

[Portfolio](https://dr01d.info/projects)

## Run locally

```text
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

See [project documentation](README.project.md) for detailed setup, architecture and limitations.

## Source snapshot

This repository contains the project source and required source assets. Local dependencies,
generated builds, runtime uploads, databases, logs and environment files are excluded.
Configure your own service credentials before using external integrations.
