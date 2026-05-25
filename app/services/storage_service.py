from io import BytesIO
from mimetypes import guess_extension
from uuid import UUID, uuid4

from minio import Minio
from minio.error import MinioException, S3Error

from app.config import settings
from app.core.exceptions import ValidationError


class MinioStorageService:
    def __init__(self):
        endpoint = settings.s3_client_endpoint
        if not endpoint:
            raise ValidationError("Не настроен адрес MinIO")
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise ValidationError("Не настроены учетные данные MinIO")
        if not settings.minio_bucket_name:
            raise ValidationError("Не настроено имя хранилища MinIO")

        self.endpoint = endpoint
        self.bucket_name = settings.minio_bucket_name
        self.client = Minio(
            endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )

    def healthcheck(self) -> dict[str, str | bool]:
        self._ensure_bucket_exists(self.bucket_name)

        return {
            "status": "ok",
            "bucket_exists": True,
            "endpoint": self.endpoint,
            "bucket_name": self.bucket_name,
        }

    def upload_object(
        self,
        *,
        user_id: UUID,
        file_bytes: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> dict[str, str]:
        if not file_bytes:
            raise ValidationError("Загруженный файл пустой")

        self._ensure_bucket_exists(self.bucket_name)

        normalized_content_type = content_type or "application/octet-stream"
        object_key = self._build_object_key(
            user_id=user_id,
            filename=filename,
            content_type=normalized_content_type,
        )

        payload = BytesIO(file_bytes)
        try:
            self.client.put_object(
                self.bucket_name,
                object_key,
                payload,
                length=len(file_bytes),
                content_type=normalized_content_type,
            )
        except (S3Error, MinioException, Exception) as exc:
            raise ValidationError(f"Ошибка загрузки в MinIO: {exc}") from exc

        return {
            "object_key": object_key,
            "url": self.build_public_url(object_key),
        }

    def upload_product_image(
        self,
        *,
        uploader_id: UUID,
        file_bytes: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> dict[str, str]:
        bucket_name = settings.minio_product_bucket_name
        if not bucket_name:
            raise ValidationError("Не настроено имя хранилища для фото товаров")
        if not file_bytes:
            raise ValidationError("Загруженный файл пустой")

        normalized_content_type = content_type or "application/octet-stream"
        if not normalized_content_type.startswith("image/"):
            raise ValidationError("Поддерживается загрузка только изображений")

        self._ensure_bucket_exists(bucket_name)
        object_key = self._build_product_object_key(
            uploader_id=uploader_id,
            filename=filename,
            content_type=normalized_content_type,
        )

        payload = BytesIO(file_bytes)
        try:
            self.client.put_object(
                bucket_name,
                object_key,
                payload,
                length=len(file_bytes),
                content_type=normalized_content_type,
            )
        except (S3Error, MinioException, Exception) as exc:
            raise ValidationError(f"Ошибка загрузки фото товара в MinIO: {exc}") from exc

        return {
            "object_key": object_key,
            "url": self.build_public_url(object_key, bucket_name=bucket_name),
        }

    def download_object(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket_name, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except (S3Error, MinioException, Exception) as exc:
            raise ValidationError(f"Ошибка скачивания из MinIO: {exc}") from exc

    def delete_object(self, object_key: str) -> None:
        try:
            self.client.remove_object(self.bucket_name, object_key)
        except S3Error as exc:
            if getattr(exc, "code", None) == "NoSuchKey":
                return
            raise ValidationError(f"Ошибка удаления из MinIO: {exc}") from exc
        except (MinioException, Exception) as exc:
            raise ValidationError(f"Ошибка удаления из MinIO: {exc}") from exc

    def build_public_url(self, object_key: str, bucket_name: str | None = None) -> str:
        if settings.minio_public_endpoint:
            base = settings.minio_public_endpoint.rstrip("/")
        elif settings.minio_public_host:
            scheme = "https" if (settings.minio_public_port in (443, None)) else "http"
            suffix = "" if settings.minio_public_port in (80, 443, None) else f":{settings.minio_public_port}"
            base = f"{scheme}://{settings.minio_public_host}{suffix}"
        else:
            scheme = "https" if settings.s3_secure else "http"
            base = f"{scheme}://{self.endpoint}"

        return self._compose_public_url(
            base=base,
            bucket_name=bucket_name or self.bucket_name,
            object_key=object_key,
        )

    def _compose_public_url(self, *, base: str, bucket_name: str, object_key: str) -> str:
        return f"{base}/{bucket_name}/{object_key}"

    def _build_object_key(self, *, user_id: UUID, filename: str | None, content_type: str) -> str:
        extension = ""
        if filename and "." in filename:
            extension = "." + filename.rsplit(".", 1)[-1].lower()
        if not extension:
            guessed = guess_extension(content_type.split(";")[0].strip())
            extension = guessed or ".bin"

        return f"inmates/{user_id}/profile/{uuid4().hex}{extension}"

    def _build_product_object_key(self, *, uploader_id: UUID, filename: str | None, content_type: str) -> str:
        extension = ""
        if filename and "." in filename:
            extension = "." + filename.rsplit(".", 1)[-1].lower()
        if not extension:
            guessed = guess_extension(content_type.split(";")[0].strip())
            extension = guessed or ".bin"
        return f"products/{uploader_id}/{uuid4().hex}{extension}"

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            bucket_exists = self.client.bucket_exists(bucket_name)
        except (S3Error, MinioException, Exception) as exc:
            raise ValidationError(f"Не удалось подключиться к MinIO: {exc}") from exc

        if not bucket_exists:
            raise ValidationError(f"Хранилище MinIO '{bucket_name}' не существует")
