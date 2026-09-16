import pytest
from django.contrib.contenttypes.models import ContentType

from core.models import Media
from core.models import Post

pytestmark = pytest.mark.django_db


def test_vkvideo_link_is_saved_and_classified_as_video():
    post = Post.objects.create(title="Test post", body="Body")

    media = Media(
        content_type=ContentType.objects.get_for_model(Post),
        object_id=post.id,
    )

    media.external_url = "https://vkvideo.ru/video-230414108_456239502"

    assert media.external_media is not None
    assert media.external_media.source == "vk"
    assert media.external_media.external_id == "230414108_456239502"
    assert (
        media.external_url == "https://vk.com/video_ext.php?oid=-230414108&id=456239502"
    )
    assert media.media_kind == Media.Kind.VIDEO

    media.full_clean()


def test_vkclip_link_is_saved_and_classified_as_video():
    post = Post.objects.create(title="Test post", body="Body")

    media = Media(
        content_type=ContentType.objects.get_for_model(Post),
        object_id=post.id,
    )

    media.external_url = "https://vkvideo.ru/clip-236237605_456239146"

    assert media.external_media is not None
    assert media.external_media.source == "vk"
    assert media.external_media.external_id == "236237605_456239146"
    assert (
        media.external_url == "https://vk.com/video_ext.php?oid=-236237605&id=456239146"
    )
    assert media.media_kind == Media.Kind.VIDEO

    media.full_clean()
