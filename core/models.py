from __future__ import annotations

import logging
import re
import typing
import uuid
from abc import ABC
from abc import abstractmethod
from datetime import UTC
from datetime import datetime
from pathlib import Path

import requests
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def media_url_exists(url: str, timeout: int = 3) -> bool:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code == 405:
            response = requests.get(
                url,
                stream=True,
                allow_redirects=True,
                timeout=timeout,
            )
        return response.status_code < 400
    except requests.RequestException:
        return False


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)

    def soft_delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def restore(self):
        return self.update(is_deleted=False, deleted_at=None)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def delete(self, using=None, keep_parents=False):
        self.soft_delete(using=using, keep_parents=keep_parents)


class SiteProfile(SoftDeleteModel):
    title = models.CharField(max_length=200)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    repertoire_text = models.TextField(blank=True)
    main_photo = models.ImageField(upload_to="profile/", blank=True, null=True)
    hero_media = GenericRelation("Media", related_query_name="site_profile")

    class Meta:
        verbose_name = "Профиль сайта"
        verbose_name_plural = "Профиль сайта"

    def __str__(self):
        return self.title


class ContactInfo(SoftDeleteModel):
    profile = models.OneToOneField(
        SiteProfile,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    phone = models.CharField(max_length=50, blank=True)
    whatsapp = models.CharField(max_length=100, blank=True)
    telegram = models.CharField(max_length=100, blank=True)
    vk = models.CharField(max_length=100, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=120, blank=True)
    extra_contact = models.TextField(blank=True)

    class Meta:
        verbose_name = "Контакты"
        verbose_name_plural = "Контакты"

    def __str__(self):
        return f"Контакты: {self.profile.title}"


class Post(SoftDeleteModel):
    class CarouselOrientation(models.TextChoices):
        HORIZONTAL = "h", "Горизонтальная"
        VERTICAL = "v", "Вертикальная"

    class Status(models.TextChoices):
        DRAFT = "d", "Черновик"
        PUBLISHED = "p", "Опубликован"
        ARCHIVED = "a", "Скрыт"

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    carousel_orientation = models.CharField(
        max_length=20,
        choices=CarouselOrientation.choices,
        default=CarouselOrientation.HORIZONTAL,
        help_text=_("Controls the carousel aspect ratio and layout."),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    sort_order = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(blank=True, null=True)
    media_items = GenericRelation("Media", related_query_name="post")

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().clean()


class SourceChoices(models.TextChoices):
    YOUTUBE = "y", "YouTube"
    RUTUBE = "r", "RuTube"
    VK_VIDEO = "vk", "VK Video"
    YANDEX_DISK = "yd", "Yandex Disk"
    GOOGLE_DRIVE = "g", "Google Drive"


class ExternalMediaExtender(ABC):
    source: SourceChoices
    _re: re.Pattern

    @property
    @abstractmethod
    def _embed_link_template(self) -> str:
        msg = _("Subclasses must define _embed_link_template")
        raise NotImplementedError(msg)

    def __init__(self, external: ExternalMedia | None = None):
        self.external = external

    @classmethod
    def match_link(cls, link: str) -> bool:
        return False

    def set_link(self, link: str) -> None:
        m = self._re.search(link)
        if not m:
            raise ValidationError(_("Invalid %s link") % self.source.label)
        if not self.external:
            raise ValidationError(_("Requires ExternalMedia instance"))
        self.external.source = self.source
        self.external.external_id = m.group("id")

    def get_link(self) -> str:
        if not self.external or not self.external.external_id:
            raise ValidationError(_("External id is not set"))
        return self._embed_link_template.format(external_id=self.external.external_id)


class YouTubeExtender(ExternalMediaExtender):
    source = SourceChoices.YOUTUBE
    _re = re.compile(
        r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)(?P<id>[A-Za-z0-9_-]{5,})",
    )

    @property
    def _embed_link_template(self) -> str:
        return "https://www.youtube.com/embed/{external_id}"

    @classmethod
    def match_link(cls, link: str) -> bool:
        return bool(cls._re.search(link))


class RuTubeExtender(ExternalMediaExtender):
    source = SourceChoices.RUTUBE
    _re = re.compile(r"rutube\.ru/(?:(?:video/)|(?:play/embed/))(?P<id>[A-Za-z0-9_-]+)")

    @property
    def _embed_link_template(self) -> str:
        return "https://rutube.ru/play/embed/{external_id}/"

    @classmethod
    def match_link(cls, link: str) -> bool:
        return bool(cls._re.search(link))


class VKVideoExtender(ExternalMediaExtender):
    source = SourceChoices.VK_VIDEO
    _re = re.compile(
        r"(?:https?://)?(?:www\.)?(?:vkvideo\.ru|vk\.com)/(?:video|clip)-(?P<owner>-?\d+)_(?P<id>\d+)",
    )

    @property
    def _embed_link_template(self) -> str:
        msg = _("Subclasses must define _embed_link_template")
        raise NotImplementedError(msg)

    @classmethod
    def match_link(cls, link: str) -> bool:
        return bool(cls._re.search(link))

    def set_link(self, link: str) -> None:
        m = self._re.search(link)
        if not m:
            raise ValidationError(_("Invalid %s link") % self.source.label)
        if not self.external:
            raise ValidationError(_("Requires ExternalMedia instance"))
        self.external.source = self.source
        self.external.external_id = f"{m.group('owner').lstrip('-')}_{m.group('id')}"

    def get_link(self) -> str:
        if not self.external or not self.external.external_id:
            raise ValidationError(_("External id is not set"))
        owner_id, video_id = self.external.external_id.split("_", 1)
        return f"https://vk.com/video_ext.php?oid=-{owner_id}&id={video_id}"


class YandexDiskExtender(ExternalMediaExtender):
    source = SourceChoices.YANDEX_DISK
    _re = re.compile(
        r"(?:yadi\.sk/i/|disk\.yandex\.ru/(?:i|d|public)/)(?P<id>[A-Za-z0-9_-]+)",
    )

    def __get_file_download_link(self, url):
        api_url = "https://cloud-api.yandex.net/v1"
        response = requests.get(
            f"{api_url}/disk/public/resources/download",
            params={"public_key": url},
            timeout=5,
        )
        if response.ok:
            data = response.json()
            return data.get("href")
        logger.warning(
            "Unexpected response from yandex api: [%s] %s",
            response.status_code,
            response.text,
        )
        return None

    @property
    def _embed_link_template(self) -> str:
        return self.external.direct_download_link

    @classmethod
    def match_link(cls, link: str) -> bool:
        return bool(cls._re.search(link))

    def set_link(self, link):
        super().set_link(link)
        direct_link = self.__get_file_download_link(link)
        if not direct_link:
            raise ValidationError(_("Failed to retrieve direct download link"))
        self.external.direct_download_link = direct_link


class GoogleDriveExtender(ExternalMediaExtender):
    source = SourceChoices.GOOGLE_DRIVE
    _re = re.compile(
        r"(?:https?://)?(?:www\.)?drive\.google\.com/(?:file/d/|open\?id=)(?P<id>[A-Za-z0-9_-]{10,})",
    )

    @property
    def _embed_link_template(self) -> str:
        return (
            "https://drive.usercontent.google.com/download?id={external_id}&authuser=0"
        )

    @classmethod
    def match_link(cls, link: str) -> bool:
        return bool(cls._re.search(link))


class ExternalMedia(models.Model):
    Source = SourceChoices

    source = models.CharField(max_length=32, choices=Source.choices)
    external_id = models.CharField(max_length=255)
    direct_download_link = models.URLField(
        blank=True,
        help_text=_("Direct download link for the external media."),
    )

    _extenders_mapping = {
        SourceChoices.YOUTUBE: YouTubeExtender,
        SourceChoices.RUTUBE: RuTubeExtender,
        SourceChoices.VK_VIDEO: VKVideoExtender,
        SourceChoices.YANDEX_DISK: YandexDiskExtender,
        SourceChoices.GOOGLE_DRIVE: GoogleDriveExtender,
    }

    class Meta:
        verbose_name = "External media"
        verbose_name_plural = "External media"

    def __str__(self) -> str:
        return f"{self.source}:{self.external_id}"

    def _get_extender_class_for_source(self):
        return self._extenders_mapping.get(self.source)

    def _get_extender_class_for_link(self, link: str):
        for ExtenderCls in self._extenders_mapping.values():
            if ExtenderCls.match_link(link):
                return ExtenderCls
        return None

    def clean(self):
        if not self.source or not self.external_id:
            raise ValidationError(_("External media source and id are required."))

    @property
    def link(self) -> str | None:
        ExtenderCls = self._get_extender_class_for_source()
        if not ExtenderCls:
            return None
        extender: ExternalMediaExtender = ExtenderCls(self)
        return extender.get_link()

    @link.setter
    def link(self, value: str) -> None:
        ExtenderCls = self._get_extender_class_for_link(value)
        if ExtenderCls:
            extender = ExtenderCls(self)
            extender.set_link(value)


class Media(SoftDeleteModel):
    class Kind(models.TextChoices):
        IMAGE = "i", "Фото"
        VIDEO = "v", "Видео"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    uploaded_file = models.FileField(upload_to="media/%Y/%m/%d/", blank=True, null=True)
    external_media = models.OneToOneField(
        ExternalMedia,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="media",
    )
    mime_type = models.CharField(blank=True, max_length=255)
    size = models.PositiveIntegerField(blank=True, null=True)
    is_primary = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_(
            "Designates whether this media is the primary one for the associated object.",
        ),
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]
        indexes = [models.Index(fields=["content_type", "object_id", "sort_order"])]
        verbose_name = "Медиа"
        verbose_name_plural = "Медиа"

    def __str__(self) -> str:
        parent = getattr(self, "content_object", None)
        parent_name = parent if parent is not None else "media"
        return f"{parent_name} - {self.media_kind}"

    @property
    def is_available(self) -> bool:
        if self.uploaded_file:
            return default_storage.exists(self.uploaded_file.name)
        if self.external_media:
            return True
        return self.external_url is not None

    @property
    def is_not_found(self) -> bool:
        return not self.is_available

    @property
    def media_kind(self):
        if self.uploaded_file:
            suffix = Path(self.uploaded_file.name).suffix.lower()
            if suffix in {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}:
                return self.Kind.VIDEO
            return self.Kind.IMAGE

        if self.external_url:
            if self.external_media and self.external_media.source in {
                SourceChoices.YOUTUBE,
                SourceChoices.RUTUBE,
                SourceChoices.VK_VIDEO,
            }:
                return self.Kind.VIDEO
            return self.Kind.IMAGE

        return self.Kind.IMAGE

    def clean(self):
        if not (self.uploaded_file or self.external_url):
            raise ValidationError(
                _("Either uploaded_file or external_url must be set."),
            )
        if self.uploaded_file and self.external_url:
            raise ValidationError(
                _("Only one of uploaded_file or external_url may be set."),
            )
        super().clean()

    @property
    def external_url(self):
        if self.external_media:
            return self.external_media.link
        return None

    @external_url.setter
    def external_url(self, value: str | None):
        if not value:
            self.external_media = None
            return
        external_media = self.external_media or ExternalMedia()
        external_media.link = value
        self.external_media = external_media

    @property
    def url(self) -> str | None:
        return (
            default_storage.url(self.uploaded_file.name)
            if self.uploaded_file
            else self.external_url
        )

    def _delete_file(self, filename):
        if default_storage.exists(filename):
            default_storage.delete(filename)

    @transaction.atomic
    def delete(self, *args, **kwargs):
        deletion_result = super().delete(*args, **kwargs)
        if self.uploaded_file:
            self._delete_file(self.uploaded_file.name)
        return deletion_result

    def save(self, *args, **kwargs):
        if self.external_media:
            self.external_media.save()
        super().save(*args, **kwargs)

    def get_file_suffix(self, file: typing.Any) -> str:
        return Path(file.name).suffix

    def get_filename(self, file_suffix, media_obj_id=None):
        media_obj_id = media_obj_id or uuid.uuid4()
        now = datetime.now(tz=UTC)
        return f"{now.year}/{now.month}/{now.day}/{media_obj_id}{file_suffix}"

    def save_file(self, file: typing.Any):
        file_suffix = self.get_file_suffix(file)
        filename = default_storage.save(
            name=self.get_filename(file_suffix, self.id),
            content=file.file,
        )
        self.mime_type = getattr(file, "content_type", "")
        self.size = getattr(file, "size", None)
        self.uploaded_file = filename
        self.save(update_fields=["mime_type", "size", "uploaded_file"])

    def fetch_file(self):
        if not self.uploaded_file:
            msg = _("No uploaded file associated with this media.")
            raise NotImplementedError(msg)
        return default_storage.open(self.uploaded_file.name)

    def copy(self, parent):
        self.id = None
        related_obj_type = ContentType.objects.get_for_model(parent)
        self.content_type = related_obj_type
        self.object_id = parent.id
        self.save()
        return self
