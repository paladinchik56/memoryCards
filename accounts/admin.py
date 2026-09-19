from django.contrib import admin

from .models import Friendship, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'user', 'created_at')
    search_fields = ('nickname', 'user__username', 'user__email')


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('from_user__username', 'to_user__username', 'from_user__profile__nickname', 'to_user__profile__nickname')
