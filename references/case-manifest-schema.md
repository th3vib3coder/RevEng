# Case Manifest Schema

`case_manifest.json` is the reproducibility index for a RevEng analysis case. It records the analyzed target, emitted artifacts, hard caps, helper script hashes, ignored traversal directories, and static-first safety posture.

The manifest is deterministic by default. It omits wall-clock timestamps unless `--generated-at` is provided.

## Create

```bash
python3 scripts/case_manifest.py \
  --case-dir case \
  --target /path/to/repo \
  --artifact repo_inventory=case/repo_inventory.json \
  --artifact repo_map=case/repo_map.json \
  --artifact repo_corpus=case/repo_corpus.jsonl \
  --cap repo_corpus_max_file_bytes=500000
```

On Windows, use `python` if `python3` is absent.

## Top-Level Fields

- `schema`: currently `reveng.case_manifest.v1`.
- `case_id`: deterministic ID derived from target content hash, caps, target kind, and schema. Artifact hashes are tracked separately so the same target content can keep a stable case ID across different output directories.
- `target`: analyzed input metadata.
- `artifacts`: output files produced for the case.
- `caps`: operator/script limits that affected analysis.
- `script_hashes`: SHA256 hashes of RevEng helper scripts used to create/index the case.
- `ignored_directories`: directory names skipped during repository traversal.
- `warnings`: sorted warnings supplied by the operator or orchestration layer.
- `safety`: static-first posture metadata.
- `generated_at`: optional timestamp, present only when explicitly requested.

## target

- `kind`: `source_repo` for repository analysis.
- `path`: absolute operator-provided target path.
- `path_role`: `operator_input`.
- `content_sha256`: deterministic hash over repository-relative file paths and file SHA256 values after RevEng ignore/symlink rules.

## artifacts

Each artifact has:

- `name`: stable logical name such as `repo_inventory`, `repo_map`, or `repo_corpus`.
- `path`: path relative to `case_dir` when possible; otherwise an absolute operator output path.
- `kind`: `json`, `jsonl`, `md`, `txt`, or `file`.
- `size_bytes`: artifact size.
- `sha256`: artifact content hash.

## safety

- `static_first`: always `true` for default repo analysis.
- `executed_target_code`: `false` unless a separately authorized execution gate ran.
- `network_contacted`: `false` unless a separately authorized network gate ran.

If execution or network access is required, do not silently flip these fields. Stop at PAUSE, collect authorization, and generate a new case manifest for that separately scoped phase.
