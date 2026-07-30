from django import template

register = template.Library()

@register.simple_tag
def get_avatar_url(user):
    try:
        if user.profile.avatar:
            return user.profile.avatar.url
    except Exception:
        pass
    return None
