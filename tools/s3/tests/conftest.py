"""Fixtures for the S3 behaviour tests.

The endpoint and credentials come from the environment, so the same tests run against the
local RustFS container (compose.yml) or a real provider:

    S3_ENDPOINT            endpoint URL; unset to use the provider's default endpoint
    S3_REGION              region name (default: us-east-1)
    AWS_ACCESS_KEY_ID      credentials, as read by the AWS SDK
    AWS_SECRET_ACCESS_KEY
    S3_TEST_TARGET         must be set; a short name for the store under test, such as "rustfs"

Every test creates its own uniquely named bucket and deletes it, with every version and pending
upload, at the end.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator

import boto3
import pytest
from botocore.config import Config

MIB = 1024 * 1024


def pytest_configure(config: pytest.Config) -> None:
    if not os.environ.get("S3_TEST_TARGET"):
        raise pytest.UsageError(
            "S3_TEST_TARGET is not set. Start tools/s3/compose.yml and see tools/s3/README.md."
        )


@pytest.fixture(scope="session")
def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT") or None,
        region_name=os.environ.get("S3_REGION", "us-east-1"),
        config=Config(
            s3={"addressing_style": "path"},
            retries={"max_attempts": 1},
            max_pool_connections=32,
        ),
    )


def empty_and_delete(s3, name: str) -> None:
    """Delete every version, delete marker, object, and pending upload, then the bucket."""
    versions = s3.list_object_versions(Bucket=name)
    for entry in versions.get("Versions", []) + versions.get("DeleteMarkers", []):
        s3.delete_object(Bucket=name, Key=entry["Key"], VersionId=entry["VersionId"])
    for item in s3.list_objects_v2(Bucket=name).get("Contents", []):
        s3.delete_object(Bucket=name, Key=item["Key"])
    for upload in s3.list_multipart_uploads(Bucket=name).get("Uploads", []):
        s3.abort_multipart_upload(Bucket=name, Key=upload["Key"], UploadId=upload["UploadId"])
    s3.delete_bucket(Bucket=name)


@pytest.fixture
def make_bucket(s3) -> Iterator[Callable[..., str]]:
    created: list[str] = []

    def make(versioned: bool = False) -> str:
        name = f"udc-test-{uuid.uuid4().hex[:16]}"
        s3.create_bucket(Bucket=name)
        if versioned:
            s3.put_bucket_versioning(Bucket=name, VersioningConfiguration={"Status": "Enabled"})
        created.append(name)
        return name

    yield make
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    for name in created:
        if name in existing:
            empty_and_delete(s3, name)


def http_status(error) -> int:
    return error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")


def keys(s3, bucket: str, prefix: str = "") -> list[str]:
    return [o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])]
