import re

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the big preview rendering
old_preview = '''        <!-- Баннер -->
        <div class="h-40 md:h-56 relative overflow-hidden">
            {% if current_user.active_banner %}
                <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif current_user.banner %}
                <img src="{{ current_user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>
        </div>'''

new_preview = '''        <!-- Баннер (фон) -->
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

content = content.replace(old_preview, new_preview)

# Replace the card previews rendering
old_card_preview = '''<!-- Превью баннера -->
                <div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl {% if is_locked %}opacity-60 grayscale{% endif %}">
                    <img src="{{ url_for('static', filename=banner.image) }}" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                </div>'''

new_card_preview = '''<!-- Превью баннера -->
                <div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl {% if is_locked %}opacity-60 grayscale{% endif %}">
                    <!-- Заглушка фона для превью -->
                    <div class="absolute inset-0 bg-gradient-to-br from-primary via-accent to-pink"></div>
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                    
                    <!-- Сама рамка (оверлей) -->
                    <img src="{{ url_for('static', filename=banner.image) }}" class="absolute inset-0 w-full h-full object-cover z-10">
                </div>'''

content = content.replace(old_card_preview, new_card_preview)

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'w', encoding='utf-8') as f:
    f.write(content)
