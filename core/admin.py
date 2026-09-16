from django import forms
from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import ContactInfo
from .models import ExternalMedia
from .models import Media
from .models import Post
from .models import SiteProfile


class SoftDeleteAdminMixin:
    actions = ["soft_delete_selected", "restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.action(description="Мягко удалить выбранные записи")
    def soft_delete_selected(self, request, queryset):
        queryset.update(is_deleted=True)

    @admin.action(description="Восстановить выбранные записи")
    def restore_selected(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)

    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        queryset.update(is_deleted=True)


class MediaInlineForm(forms.ModelForm):
    external_url = forms.URLField(required=False, label="Внешняя ссылка")

    class Meta:
        model = Media
        fields = (
            "uploaded_file",
            "external_url",
            "is_primary",
            "sort_order",
            "is_deleted",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["external_url"].initial = self.instance.external_url

    def clean(self):
        cleaned_data = super().clean()
        external_url = cleaned_data.get("external_url")
        uploaded_file = cleaned_data.get("uploaded_file")

        if (
            not uploaded_file
            and not external_url
            and not cleaned_data.get("is_deleted")
        ):
            raise forms.ValidationError("Нужно указать файл или внешнюю ссылку.")
        if uploaded_file and external_url:
            raise forms.ValidationError("Нужно указать только один источник медиа.")

        self.instance.external_url = external_url or None
        return cleaned_data


class MediaInline(GenericTabularInline):
    model = Media
    extra = 0
    form = MediaInlineForm
    fields = ("uploaded_file", "external_url", "is_primary", "sort_order", "is_deleted")
    readonly_fields = ("created_at", "updated_at", "deleted_at")


class MediaAdminForm(MediaInlineForm):
    class Meta(MediaInlineForm.Meta):
        fields = (
            "content_type",
            "object_id",
            "uploaded_file",
            "external_url",
            "is_primary",
            "sort_order",
            "is_deleted",
            "deleted_at",
        )


@admin.register(SiteProfile)
class SiteProfileAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "is_deleted", "created_at", "updated_at")
    search_fields = ("title", "tagline", "description")
    fields = (
        "title",
        "tagline",
        "description",
        "repertoire_text",
        "main_photo",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    inlines = [MediaInline]


@admin.register(ContactInfo)
class ContactInfoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("profile", "phone", "city", "is_deleted", "updated_at")
    search_fields = ("profile__title", "phone", "city")
    fields = (
        "profile",
        "phone",
        "whatsapp",
        "telegram",
        "vk",
        "instagram",
        "city",
        "extra_contact",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(Post)
class PostAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "carousel_orientation",
        "status",
        "sort_order",
        "is_deleted",
        "published_at",
        "updated_at",
    )
    list_filter = ("carousel_orientation", "status", "is_deleted")
    search_fields = ("title", "body")
    ordering = ("sort_order", "-created_at")
    inlines = [MediaInline]
    fields = (
        "title",
        "carousel_orientation",
        "body",
        "status",
        "sort_order",
        "published_at",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(Media)
class MediaAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    form = MediaAdminForm
    list_display = (
        "content_object",
        "media_kind",
        "sort_order",
        "is_primary",
        "is_deleted",
        "updated_at",
    )
    list_filter = ("is_deleted", "is_primary")
    search_fields = ("content_type__model",)
    fields = (
        "content_type",
        "object_id",
        "uploaded_file",
        "external_url",
        "is_primary",
        "sort_order",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at")


@admin.register(ExternalMedia)
class ExternalMediaAdmin(admin.ModelAdmin):
    list_display = ("source", "external_id", "direct_download_link")
    search_fields = ("source", "external_id")
