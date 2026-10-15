# Bounded synthetic intake v1

`intake.cjs` is the shared, browser-portable pure parser; no IO or execution.
256 KiB maximum before parsing; 1–500 records; strict UTF-8/ASCII field values.
JSON: exact envelope `schemaVersion: defence-intake/1` and `findings` array.
CSV: exact header order below; standard doubled quotes and LF/CRLF accepted.

findingId,accountAlias,resourceAlias,resourceType,region,controlId,severity,compliance,observedAt

Use [synthetic-import.json](synthetic-import.json). Only mock-a/mock-b aliases;
resource-* invented aliases, S3/SG/UNKNOWN types, fixed Singapore Region. No
private real findings. Account numbers, ARNs, credential-shaped fields, URLs,
emails and unknown columns fail without echo. Regexes cannot recognize every
possible private nickname: users/adapters must supply invented aliases only.
Do not use this parser as a general-purpose secret scrubber.

Duplicate JSON keys, prototype keys, duplicate finding IDs or resource/control
pairs, malformed dates, unsafe numbers, extra columns, invalid UTF-8 and oversized
input fail closed. Unknown controls become unknown-control, manual review only;
raw labels are not retained. 24 candidates is a catalog, not actual live coverage.
Every accepted record becomes IMPORTED_ASSERTION with NOT_VERIFIED freshness.
No claimed input provenance, credentials, approvals or provider receipts accepted.

The core2 inline parser is byte-checked against this source by the existing VM
check. Shared copies must be updated atomically in their coordinated release.
Focused checks use Node's existing assert API, no new framework. The extra cases
are justified by this new untrusted-input boundary, not a new testing program.

The scope helper uses deterministic SHA-256 only as an integrity binding, never
as authentication. Server-issued private target/actor authority is a separate gate.
