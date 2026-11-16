"""The few object-store operations the reference configuration and its tests need."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from refconf.config import Store


class S3:
    def __init__(self, store: Store) -> None:
        self.client = boto3.client(
            "s3",
            endpoint_url=store.endpoint,
            region_name=store.region,
            aws_access_key_id=store.access_key,
            aws_secret_access_key=store.secret_key,
            config=Config(s3={"addressing_style": "path"}, max_pool_connections=16),
        )

    def keys(self, bucket: str, prefix: str = "") -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield item["Key"]

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            if error.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise
        return True

    def put(self, bucket: str, key: str, body: bytes) -> None:
        self.client.put_object(Bucket=bucket, Key=key, Body=body)

    def copy(self, bucket: str, source_key: str, dest_key: str) -> None:
        self.client.copy_object(
            Bucket=bucket, Key=dest_key, CopySource={"Bucket": bucket, "Key": source_key}
        )

    def delete_prefix(self, bucket: str, prefix: str = "") -> int:
        keys = list(self.keys(bucket, prefix))
        for start in range(0, len(keys), 1000):
            batch = keys[start : start + 1000]
            self.client.delete_objects(
                Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True}
            )
        return len(keys)

    def pending_uploads(self, bucket: str, prefix: str = "") -> int:
        response = self.client.list_multipart_uploads(Bucket=bucket, Prefix=prefix)
        return len(response.get("Uploads", []))

    def abort_uploads(self, bucket: str, prefix: str = "") -> int:
        uploads = self.client.list_multipart_uploads(Bucket=bucket, Prefix=prefix)
        for upload in uploads.get("Uploads", []):
            self.client.abort_multipart_upload(
                Bucket=bucket, Key=upload["Key"], UploadId=upload["UploadId"]
            )
        return len(uploads.get("Uploads", []))

    def reset_bucket(self, bucket: str) -> None:
        """Create the bucket, or empty it of objects and pending uploads if it exists."""
        try:
            self.client.create_bucket(Bucket=bucket)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise
        self.delete_prefix(bucket)
        self.abort_uploads(bucket)

    def delete_bucket(self, bucket: str) -> None:
        self.delete_prefix(bucket, "")
        self.abort_uploads(bucket)
        self.client.delete_bucket(Bucket=bucket)
