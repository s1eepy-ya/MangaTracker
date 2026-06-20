import re

with open('c:/Users/lizae/Downloads/MangaTracker/templates/profile.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_header = '''        <!-- Баннер -->
        <div class="h-56 md:h-72 relative overflow-hidden rounded-t-3xl">
            {% if user.active_banner %}
                <img src="{{ url_for('static', filename=user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif user.banner %}
                <img src="{{ user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}'''

new_header = '''        <!-- Баннер -->
        <div class="h-56 md:h-72 relative overflow-hidden rounded-t-3xl">
            {% if user.banner %}
                <img src="{{ user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}'''

content = content.replace(old_header, new_header)

old_card = '<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8">'

new_card = '''<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8 mt-12 md:mt-16 mx-4 md:mx-10">
        {% if user.active_banner %}
            <!-- Рамка профиля (баннер) -->
            <img src="{{ url_for('static', filename=user.active_banner.image) }}" class="absolute -inset-[30px] md:-inset-[40px] w-[calc(100%+60px)] md:w-[calc(100%+80px)] h-[calc(100%+60px)] md:h-[calc(100%+80px)] z-50 pointer-events-none" style="object-fit: fill;" alt="Profile Frame">
        {% endif %}'''

content = content.replace(old_card, new_card)

with open('c:/Users/lizae/Downloads/MangaTracker/templates/profile.html', 'w', encoding='utf-8') as f:
    f.write(content)

# Now fix banners_shop.html preview
with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'r', encoding='utf-8') as f:
    content2 = f.read()

old_preview = '''        <!-- Баннер -->
        <div class="h-40 md:h-56 relative overflow-hidden rounded-t-3xl">
            {% if current_user.active_banner %}
                <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif current_user.banner %}
                <img src="{{ current_user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}'''

new_preview = '''        <!-- Баннер -->
        <div class="h-40 md:h-56 relative overflow-hidden rounded-t-3xl">
            {% if current_user.banner %}
                <img src="{{ current_user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}'''

content2 = content2.replace(old_preview, new_preview)

old_card2 = '<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8">'

new_card2 = '''<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8 mt-12 md:mt-16 mx-4 md:mx-10">
        {% if current_user.active_banner %}
            <!-- Рамка профиля (баннер) -->
            <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="absolute -inset-[30px] md:-inset-[40px] w-[calc(100%+60px)] md:w-[calc(100%+80px)] h-[calc(100%+60px)] md:h-[calc(100%+80px)] z-50 pointer-events-none" style="object-fit: fill;" alt="Profile Frame">
        {% endif %}'''

content2 = content2.replace(old_card2, new_card2)

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'w', encoding='utf-8') as f:
    f.write(content2)

