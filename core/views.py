from django.shortcuts import render

from .models import ContactInfo
from .models import Media
from .models import Post
from .models import SiteProfile
from .text_rendering import render_markdown_text


def _media_payload(media):
    return {
        "kind": media.media_kind,
        "url": media.url,
        "title": getattr(media.content_object, "title", "Медиа"),
        "is_external": media.external_url is not None,
    }


def home(request):
    profile = SiteProfile.objects.prefetch_related("hero_media").first()
    contacts = ContactInfo.objects.select_related("profile").first()
    posts = Post.objects.prefetch_related("media_items").filter(
        status=Post.Status.PUBLISHED,
    )

    hero_slides = []
    if profile:
        if profile.main_photo:
            hero_slides.append(
                {
                    "kind": Media.Kind.IMAGE,
                    "url": profile.main_photo.url,
                    "title": profile.title,
                    "is_external": False,
                },
            )
        for media in profile.hero_media.order_by("sort_order", "created_at"):
            if media.media_kind != Media.Kind.IMAGE:
                continue
            if not media.is_available:
                continue
            hero_slides.append(_media_payload(media))

    for post in posts:
        post.rendered_body = render_markdown_text(post.body)
        post.available_media_items = list(
            post.media_items.order_by("sort_order", "created_at"),
        )

    return render(
        request,
        "core/home.html",
        {
            "profile": profile,
            "contacts": contacts,
            "posts": posts,
            "hero_slides": hero_slides,
        },
    )
