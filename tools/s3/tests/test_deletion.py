"""Deletion and cleanup: what an interrupted job leaves behind, and how it is removed.

Used by the interruption tests of the first evidence gate (PRD, "Value hypotheses and evidence
gates", H2), by withdrawal and staging cleanup (ADR-0017), and by every test that tears down a
bucket.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError
from conftest import MIB, http_status, keys


def test_single_delete_removes_the_object(s3, make_bucket):
    b = make_bucket()
    s3.put_object(Bucket=b, Key="out/part-0.parquet", Body=b"x")
    s3.delete_object(Bucket=b, Key="out/part-0.parquet")
    with pytest.raises(ClientError) as raised:
        s3.head_object(Bucket=b, Key="out/part-0.parquet")
    assert http_status(raised.value) == 404


def test_batch_delete_removes_a_prefix(s3, make_bucket):
    b = make_bucket()
    for i in range(5):
        s3.put_object(Bucket=b, Key=f"out/part-{i}.parquet", Body=b"x")
    s3.put_object(Bucket=b, Key="other/keep", Body=b"x")
    result = s3.delete_objects(
        Bucket=b, Delete={"Objects": [{"Key": k} for k in keys(s3, b, "out/")]}
    )
    assert not result.get("Errors")
    assert keys(s3, b, "out/") == []
    assert keys(s3, b) == ["other/keep"]


def test_deleting_a_missing_key_succeeds(s3, make_bucket):
    b = make_bucket()
    response = s3.delete_object(Bucket=b, Key="never-existed")
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 204


def test_interrupted_multipart_upload_is_pending_and_invisible(s3, make_bucket):
    b = make_bucket()
    upload = s3.create_multipart_upload(Bucket=b, Key="out/big.parquet")
    s3.upload_part(
        Bucket=b,
        Key="out/big.parquet",
        UploadId=upload["UploadId"],
        PartNumber=1,
        Body=b"a" * 5 * MIB,
    )
    pending = [u["UploadId"] for u in s3.list_multipart_uploads(Bucket=b).get("Uploads", [])]
    assert upload["UploadId"] in pending
    assert "out/big.parquet" not in keys(s3, b)


def test_abort_removes_a_pending_upload(s3, make_bucket):
    b = make_bucket()
    upload = s3.create_multipart_upload(Bucket=b, Key="out/big.parquet")
    s3.upload_part(
        Bucket=b, Key="out/big.parquet", UploadId=upload["UploadId"], PartNumber=1, Body=b"a"
    )
    s3.abort_multipart_upload(Bucket=b, Key="out/big.parquet", UploadId=upload["UploadId"])
    assert s3.list_multipart_uploads(Bucket=b).get("Uploads", []) == []
    with pytest.raises(ClientError) as raised:
        s3.upload_part(
            Bucket=b, Key="out/big.parquet", UploadId=upload["UploadId"], PartNumber=2, Body=b"b"
        )
    assert http_status(raised.value) == 404


def test_a_bucket_must_be_empty_to_be_deleted(s3, make_bucket):
    b = make_bucket()
    s3.put_object(Bucket=b, Key="left-behind", Body=b"x")
    with pytest.raises(ClientError) as raised:
        s3.delete_bucket(Bucket=b)
    assert http_status(raised.value) == 409
    s3.delete_object(Bucket=b, Key="left-behind")
    s3.delete_bucket(Bucket=b)
    assert b not in {x["Name"] for x in s3.list_buckets()["Buckets"]}


def test_versioned_delete_keeps_versions_until_each_is_deleted(s3, make_bucket):
    b = make_bucket(versioned=True)
    s3.put_object(Bucket=b, Key="k", Body=b"one")
    s3.put_object(Bucket=b, Key="k", Body=b"two")
    s3.delete_object(Bucket=b, Key="k")

    listing = s3.list_object_versions(Bucket=b)
    assert len(listing.get("Versions", [])) == 2
    assert len(listing.get("DeleteMarkers", [])) == 1
    assert keys(s3, b) == []
    with pytest.raises(ClientError) as raised:
        s3.delete_bucket(Bucket=b)
    assert http_status(raised.value) == 409

    for entry in listing["Versions"] + listing["DeleteMarkers"]:
        s3.delete_object(Bucket=b, Key=entry["Key"], VersionId=entry["VersionId"])
    after = s3.list_object_versions(Bucket=b)
    assert not after.get("Versions")
    assert not after.get("DeleteMarkers")
    s3.delete_bucket(Bucket=b)
