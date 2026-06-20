import re

# Fix profile.html
with open('c:/Users/lizae/Downloads/MangaTracker/templates/profile.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_banner_html = '''        <!-- Баннер (фон) -->
        <div class="h-56 md:h-72 relative overflow-hidden">
            {% if user.banner %}
                <img src="{{ user.banner }}" class="absolute inset-0 w-full h-full object-cover" alt="Background">
            {% else %}
                <div class="absolute inset-0 bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            
            <!-- Затемнение снизу баннера -->
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>
            
            <!-- Рамка баннера (из магазина) -->
            {% if user.active_banner %}
                <img src="{{ url_for('static', filename=user.active_banner.image) }}" class="absolute inset-0 w-full h-full object-cover z-10 pointer-events-none" alt="Banner Frame">
            {% endif %}'''

new_banner_html = '''        <!-- Баннер -->
        <div class="h-56 md:h-72 relative overflow-hidden">
            {% if user.active_banner %}
                <img src="{{ url_for('static', filename=user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif user.banner %}
                <img src="{{ user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            
            <!-- Затемнение снизу баннера -->
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>'''

content = content.replace(old_banner_html, new_banner_html)

# ALSO fix overflow-hidden on the main card!
content = content.replace('<div class="relative bg-cardBg rounded-3xl border border-borderDark overflow-hidden shadow-2xl mb-8">', '<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8">')
# but if I remove overflow-hidden from the main card, the banner corners will not be rounded!
# I need to add rounded-t-3xl to the banner div.
content = content.replace('<div class="h-56 md:h-72 relative overflow-hidden">', '<div class="h-56 md:h-72 relative overflow-hidden rounded-t-3xl">')

with open('c:/Users/lizae/Downloads/MangaTracker/templates/profile.html', 'w', encoding='utf-8') as f:
    f.write(content)

# Fix banners_shop.html
with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'r', encoding='utf-8') as f:
    content2 = f.read()

old_preview = '''        <!-- Баннер (фон) -->
        <div class="h-40 md:h-56 relative overflow-hidden">
            {% if current_user.banner %}
                <img src="{{ current_user.banner }}" class="absolute inset-0 w-full h-full object-cover" alt="Background">
            {% else %}
                <div class="absolute inset-0 bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>
            
            <!-- Рамка баннера (оверлей) -->
            {% if current_user.active_banner %}
                <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="absolute inset-0 w-full h-full object-cover z-10 pointer-events-none" alt="Banner Frame">
            {% endif %}
        </div>'''

new_preview = '''        <!-- Баннер -->
        <div class="h-40 md:h-56 relative overflow-hidden rounded-t-3xl">
            {% if current_user.active_banner %}
                <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif current_user.banner %}
                <img src="{{ current_user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>
        </div>'''

content2 = content2.replace(old_preview, new_preview)

old_card = '''<!-- Превью баннера -->
                <div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl {% if is_locked %}opacity-60 grayscale{% endif %}">
                    <!-- Заглушка фона для превью -->
                    <div class="absolute inset-0 bg-gradient-to-br from-primary via-accent to-pink"></div>
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                    
                    <!-- Сама рамка (оверлей) -->
                    <img src="{{ url_for('static', filename=banner.image) }}" class="absolute inset-0 w-full h-full object-cover z-10">
                </div>'''

new_card = '''<!-- Превью баннера -->
                <div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl {% if is_locked %}opacity-60 grayscale{% endif %}">
                    <img src="{{ url_for('static', filename=banner.image) }}" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                </div>'''

content2 = content2.replace(old_card, new_card)

# ALSO fix overflow-hidden on the main card in banners_shop!
content2 = content2.replace('<div class="relative bg-cardBg rounded-3xl border border-borderDark overflow-hidden shadow-2xl mb-8">', '<div class="relative bg-cardBg rounded-3xl border border-borderDark shadow-2xl mb-8">')

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'w', encoding='utf-8') as f:
    f.write(content2)
