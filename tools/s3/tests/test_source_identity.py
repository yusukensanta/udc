"""Source identity and the consistency classes (ADR-0012, "Source identity and consistency")."""

from __future__ import annotations

import hashlib

import pytest
from botocore.exceptions import ClientError
from conftest import MIB, http_status

PRECONDITION_FAILED = 412


def test_reads_conditional_on_the_recorded_etag_fail_after_replacement(s3, make_bucket):
    """Checked class: every read, including a range read, carries the recorded ETag."""
    b = make_bucket()
    recorded = s3.put_object(Bucket=b, Key="src/data.csv", Body=b"a,b\n1,2\n")["ETag"]
    assert s3.get_object(Bucket=b, Key="src/data.csv", IfMatch=recorded)["Body"].read()

    s3.put_object(Bucket=b, Key="src/data.csv", Body=b"a,b\n9,9\n")
    with pytest.raises(ClientError) as whole:
        s3.get_object(Bucket=b, Key="src/data.csv", IfMatch=recorded)
    assert http_status(whole.value) == PRECONDITION_FAILED
    with pytest.raises(ClientError) as ranged:
        s3.get_object(Bucket=b, Key="src/data.csv", IfMatch=recorded, Range="bytes=0-3")
    assert http_status(ranged.value) == PRECONDITION_FAILED


def test_single_part_etag_is_the_md5_of_the_content(s3, make_bucket):
    b = make_bucket()
    etag = s3.put_object(Bucket=b, Key="src/single", Body=b"hello")["ETag"].strip('"')
    assert etag == hashlib.md5(b"hello").hexdigest()


def test_multipart_etag_is_not_an_md5(s3, make_bucket):
    """Why an ETag is used only as a change validator, never as a checksum."""
    b = make_bucket()
    upload = s3.create_multipart_upload(Bucket=b, Key="src/multi")
    parts = []
    for number, body in ((1, b"a" * 5 * MIB), (2, b"tail")):
        part = s3.upload_part(
            Bucket=b, Key="src/multi", UploadId=upload["UploadId"], PartNumber=number, Body=body
        )
        parts.append({"ETag": part["ETag"], "PartNumber": number})
    done = s3.complete_multipart_upload(
        Bucket=b, Key="src/multi", UploadId=upload["UploadId"], MultipartUpload={"Parts": parts}
    )
    etag = done["ETag"].strip('"')
    assert etag.endswith("-2")
    assert etag != hashlib.md5(b"a" * 5 * MIB + b"tail").hexdigest()


def test_a_recorded_version_stays_readable_after_an_overwrite(s3, make_bucket):
    """Pinned class: with versioning, the job reads the version recorded at planning."""
    b = make_bucket(versioned=True)
    first = s3.put_object(Bucket=b, Key="src/data.csv", Body=b"version-1")
    s3.put_object(Bucket=b, Key="src/data.csv", Body=b"version-2")
    assert first.get("VersionId")
    old = s3.get_object(Bucket=b, Key="src/data.csv", VersionId=first["VersionId"])
    assert old["Body"].read() == b"version-1"
