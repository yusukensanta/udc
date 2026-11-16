# S3 behaviour tests

Tests of the S3 behaviours that UDC's design relies on, and a disposable local store to run them against.

| Tests | What they check | Used by |
|---|---|---|
| `test_deletion.py` | Deleting objects, prefixes, versions, and pending multipart uploads; what an interrupted upload leaves behind | The interruption tests of the first evidence gate (PRD §13.3, H2); withdrawal and staging cleanup (ADR-0017) |
| `test_publication.py` | No-replace writes by PutObject, CompleteMultipartUpload, and CopyObject; concurrent claims; checksums across a copy; conditional update of a reference | Promotion and Reference modes (ADR-0017) |
| `test_source_identity.py` | Reads conditional on an ETag, including range reads; ETag versus MD5; reading a recorded version | The source consistency classes (ADR-0012) |

The expected results follow the Amazon S3 documentation. A test that fails against a store shows where that store differs, which is what the storage capability descriptor has to report (ADR-0005). Passing against the local store does not show that a cloud provider behaves the same way; each provider is tested separately.

## Local store

[`compose.yml`](compose.yml) runs [RustFS](https://github.com/rustfs/rustfs), an S3-compatible store, pinned by image digest. Its data lives in tmpfs, so stopping it removes every bucket. It listens on `127.0.0.1:19000` only, and its credentials are fixed test values, not secrets.

```sh
cd tools/s3
docker compose up -d --wait
S3_TEST_TARGET=rustfs S3_ENDPOINT=http://127.0.0.1:19000 \
AWS_ACCESS_KEY_ID=udc-local-access AWS_SECRET_ACCESS_KEY=udc-local-secret \
  uv run pytest
docker compose down -v
```

Set `UDC_S3_PORT` to use another host port.

## A real provider

Leave `S3_ENDPOINT` unset, set `S3_REGION`, and use credentials for an account where the tests may create and delete buckets named `udc-test-*`. Set `S3_TEST_TARGET` to a name for the provider, such as `aws-s3`. Never run the tests with credentials that can reach production data.
