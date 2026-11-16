"""Primitives of the Promotion and Reference publication modes (ADR-0017)."""

from __future__ import annotations

import concurrent.futures

import pytest
from botocore.exceptions import ClientError
from conftest import http_status

PRECONDITION_FAILED = 412
# S3 documents 409 for a conditional write that races a concurrent delete.
LOST_RACE = {PRECONDITION_FAILED, 409}


def test_put_if_none_match_creates_once(s3, make_bucket):
    b = make_bucket()
    s3.put_object(Bucket=b, Key="dest/_UDC_CLAIM", Body=b"{}", IfNoneMatch="*")
    with pytest.raises(ClientError) as raised:
        s3.put_object(Bucket=b, Key="dest/_UDC_CLAIM", Body=b"{}", IfNoneMatch="*")
    assert http_status(raised.value) == PRECONDITION_FAILED


def test_concurrent_claims_have_exactly_one_winner(s3, make_bucket):
    """The destination claim admits one publication at a time.

    ADR-0017, "Destination preconditions".
    """
    b = make_bucket()
    rounds, writers = 20, 16
    for r in range(rounds):
        key = f"round-{r}/_UDC_CLAIM"

        def claim(i: int, key: str = key) -> int | str:
            try:
                s3.put_object(Bucket=b, Key=key, Body=str(i).encode(), IfNoneMatch="*")
                return i
            except ClientError as error:
                return f"lost:{http_status(error)}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=writers) as pool:
            outcomes = list(pool.map(claim, range(writers)))
        winners = [o for o in outcomes if isinstance(o, int)]
        losers = {o for o in outcomes if isinstance(o, str)}
        assert len(winners) == 1, (r, outcomes)
        assert losers <= {f"lost:{code}" for code in LOST_RACE}, (r, losers)
        stored = s3.get_object(Bucket=b, Key=key)["Body"].read().decode()
        assert stored == str(winners[0]), (r, stored, winners)


def test_complete_multipart_if_none_match_does_not_replace(s3, make_bucket):
    b = make_bucket()
    s3.put_object(Bucket=b, Key="dest/part-0.parquet", Body=b"old")
    upload = s3.create_multipart_upload(Bucket=b, Key="dest/part-0.parquet")
    part = s3.upload_part(
        Bucket=b, Key="dest/part-0.parquet", UploadId=upload["UploadId"], PartNumber=1, Body=b"new"
    )
    with pytest.raises(ClientError) as raised:
        s3.complete_multipart_upload(
            Bucket=b,
            Key="dest/part-0.parquet",
            UploadId=upload["UploadId"],
            MultipartUpload={"Parts": [{"ETag": part["ETag"], "PartNumber": 1}]},
            IfNoneMatch="*",
        )
    assert http_status(raised.value) == PRECONDITION_FAILED
    assert s3.get_object(Bucket=b, Key="dest/part-0.parquet")["Body"].read() == b"old"


def test_copy_if_none_match_places_once_and_keeps_the_checksum(s3, make_bucket):
    """Placement is a no-replace copy, verified by checksum (ADR-0017, "Placing an object")."""
    b = make_bucket()
    s3.put_object(
        Bucket=b, Key="staging/a1/part-0.parquet", Body=b"staged", ChecksumAlgorithm="CRC32C"
    )
    source = {"Bucket": b, "Key": "staging/a1/part-0.parquet"}
    s3.copy_object(Bucket=b, Key="dest/part-0.parquet", CopySource=source, IfNoneMatch="*")
    with pytest.raises(ClientError) as raised:
        s3.copy_object(Bucket=b, Key="dest/part-0.parquet", CopySource=source, IfNoneMatch="*")
    assert http_status(raised.value) == PRECONDITION_FAILED

    staged = s3.head_object(Bucket=b, Key="staging/a1/part-0.parquet", ChecksumMode="ENABLED")
    placed = s3.head_object(Bucket=b, Key="dest/part-0.parquet", ChecksumMode="ENABLED")
    assert staged.get("ChecksumCRC32C")
    assert placed.get("ChecksumCRC32C") == staged["ChecksumCRC32C"]


def test_put_if_match_updates_a_reference_only_from_the_expected_version(s3, make_bucket):
    """The conditional update behind Reference mode (ADR-0017, "Commit")."""
    b = make_bucket()
    first = s3.put_object(Bucket=b, Key="dest/_reference", Body=b"manifest-1")
    s3.put_object(Bucket=b, Key="dest/_reference", Body=b"manifest-2", IfMatch=first["ETag"])
    with pytest.raises(ClientError) as raised:
        s3.put_object(Bucket=b, Key="dest/_reference", Body=b"manifest-3", IfMatch=first["ETag"])
    assert http_status(raised.value) == PRECONDITION_FAILED
    assert s3.get_object(Bucket=b, Key="dest/_reference")["Body"].read() == b"manifest-2"
