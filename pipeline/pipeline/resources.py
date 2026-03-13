import io
import json

import dagster as dg
from minio import Minio
from minio.error import S3Error


class MinIOResource(dg.ConfigurableResource):
    """Wraps the MinIO Python client for use in Dagster assets."""

    endpoint: str
    access_key: str
    secret_key: str
    secure: bool = False

    def _client(self) -> Minio:
        return Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def ensure_bucket(self, bucket: str) -> None:
        client = self._client()
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    def put_json(self, bucket: str, key: str, data: dict | list) -> None:
        client = self._client()
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(payload),
            length=len(payload),
            content_type="application/json",
        )

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        client = self._client()
        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_json(self, bucket: str, key: str) -> dict | list:
        client = self._client()
        response = client.get_object(bucket_name=bucket, object_name=key)
        return json.loads(response.read())

    def get_bytes(self, bucket: str, key: str) -> bytes:
        client = self._client()
        response = client.get_object(bucket_name=bucket, object_name=key)
        return response.read()

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        client = self._client()
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    def object_exists(self, bucket: str, key: str) -> bool:
        client = self._client()
        try:
            client.stat_object(bucket, key)
            return True
        except S3Error:
            return False
