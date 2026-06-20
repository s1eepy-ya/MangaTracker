import re

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the PREVIEW section
preview_start = content.find('<!-- ====== ПРЕВЬЮ ТЕКУЩЕГО ВИДА ====== -->')
preview_end = content.find('<!-- ====== ИНФО О РЕДКОСТИ ====== -->')

new_preview = '''<!-- ====== ПРЕВЬЮ ТЕКУЩЕГО ВИДА ====== -->
    <div class="relative bg-cardBg rounded-3xl border border-borderDark overflow-hidden shadow-2xl mb-8">
        <!-- Баннер -->
        <div class="h-40 md:h-56 relative overflow-hidden">
            {% if current_user.active_banner %}
                <img src="{{ url_for('static', filename=current_user.active_banner.image) }}" class="w-full h-full object-cover" alt="Banner">
            {% elif current_user.banner %}
                <img src="{{ current_user.banner }}" class="w-full h-full object-cover" alt="Banner">
            {% else %}
                <div class="w-full h-full bg-gradient-to-br from-primary via-accent to-pink"></div>
            {% endif %}
            <div class="absolute inset-0 bg-gradient-to-t from-cardBg via-cardBg/40 to-transparent"></div>
        </div>
        
        <div class="px-6 md:px-10 pb-6 -mt-16 relative z-10 flex flex-col md:flex-row md:items-end gap-6">
            <div class="avatar-wrapper avatar-lg mx-auto md:mx-0">
                <div class="avatar-inner">
                    {% if current_user.avatar %}
                        <img src="{{ current_user.avatar }}" alt="">
                    {% else %}
                        <div class="w-full h-full bg-gradient-to-br from-primary to-indigo-600 flex items-center justify-center text-3xl font-extrabold text-white">
                            {{ current_user.username[0]|upper }}
                        </div>
                    {% endif %}
                </div>
                {% if current_user.active_frame %}
                    <img src="{{ url_for('static', filename=current_user.active_frame.image) }}" class="avatar-frame animated {{ current_user.active_frame.glow_class or 'glow-blue' }}" alt="frame">
                {% endif %}
            </div>
            
            <div class="flex-1 text-center md:text-left">
                <h2 class="text-2xl font-black text-white mb-2">{{ current_user.username }}</h2>
                <div class="mb-2">
                    {% if current_user.active_banner %}
                        <span class="inline-flex items-center gap-2 px-3 py-1 bg-blue-500/15 border border-blue-500/40 text-blue-300 text-xs font-semibold rounded-full">
                            🖼️ Активный баннер: «{{ current_user.active_banner.name }}»
                        </span>
                    {% else %}
                        <span class="inline-flex items-center gap-2 px-3 py-1 bg-gray-700/40 border border-gray-600/40 text-gray-400 text-xs font-semibold rounded-full">
                            Без баннера
                        </span>
                    {% endif %}
                </div>
                {% if current_user.active_banner %}
                <form method="POST" action="{{ url_for('remove_active_banner') }}" class="inline-block">
                    <button type="submit" class="px-4 py-1.5 bg-red-600/20 text-red-300 border border-red-500/40 rounded-xl hover:bg-red-600/40 transition text-xs font-semibold">
                        🗑 Снять баннер
                    </button>
                </form>
                {% endif %}
            </div>
        </div>
    </div>
    
    '''

content = content[:preview_start] + new_preview + content[preview_end:]

# Also fix the cards to show banner preview instead of avatar-wrapper
cards_start = content.find('<!-- Карточка "Без баннера" -->')
# We need to change the preview block inside each card to show a mini banner
content = re.sub(
    r'<div class="flex justify-center mb-4.*?</div>\s+</div>\s+</div>',
    r'''<div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl">
                    <div class="w-full h-full bg-gradient-to-br from-primary to-indigo-600"></div>
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                </div>''',
    content, count=1, flags=re.DOTALL
)

content = re.sub(
    r'<!-- Превью баннера -->.*?<div class="flex justify-center mb-4.*?</div>\s+</div>\s+</div>',
    r'''<!-- Превью баннера -->
                <div class="h-24 -mx-5 -mt-5 mb-4 relative overflow-hidden rounded-t-2xl {% if is_locked %}opacity-60 grayscale{% endif %}">
                    <img src="{{ url_for('static', filename=banner.image) }}" class="w-full h-full object-cover">
                    <div class="absolute inset-0 bg-gradient-to-t from-cardBg to-transparent"></div>
                </div>''',
    content, flags=re.DOTALL
)

# And fix "Без баннера" text
content = content.replace('Без баннериа', 'Без баннера')
content = content.replace('Без рамки', 'Без баннера')

with open('c:/Users/lizae/Downloads/MangaTracker/templates/banners_shop.html', 'w', encoding='utf-8') as f:
    f.write(content)
