# Phase: extract

Dispatch prompt for `doc-ingest-extractor`.

## Read first
- `docs/implr/config/implr.config.yaml`

## Your scope
```
file_path: {{FILE_PATH}}
slug: {{SLUG}}
```

## Task
If file to extract is *.md just copy it to cache.
Extract text from `{{FILE_PATH}}` per the format rules in your system prompt. Write to
`docs/implr/kb-index/cache/{{SLUG}}.md`. If the format is unsupported or extraction fails,
do not write a cache file; return the appropriate status.


## Return summary
```
slug: {{SLUG}}
cache_path: <path or empty>
word_count: <n>
status: extracted | unsupported | extraction_failed
error: <if extraction_failed>
```
