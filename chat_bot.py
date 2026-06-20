import re
from datetime import datetime, timedelta
from models import db, ChatMessage, ChatMute, User

# Список запрещённых слов (расширьте при необходимости)
TOXIC_WORDS = [
    # Оскорбления
    'идиот', 'дурак', 'тупой', 'тупица', 'кретин', 'дебил', 'придурок',
    'мудак', 'урод', 'чмо', 'лох', 'козел', 'козёл', 'свинья', 'тварь',
    'ничтожество', 'отброс', 'выродок',
    # Маты (корни)
    'блять', 'блядь', 'бля', 'сука', 'сучка', 'хуй', 'хуё', 'хуе',
    'пизд', 'еба', 'ебан', 'ёбан', 'ебал', 'ебать', 'ёбаный',
    'пидор', 'пидар', 'гандон', 'шлюх', 'шлюш', 'ублюд', 'мраз',
    'нахуй', 'похуй',
]

TOXIC_PATTERNS = [
    r'\bн[аa@]х[уy][йi1]?\b',
    r'\bи?д[иi1][оo0]т\b',
    r'\bт[уy]п[оo0][йi]?\b',
    r'\bхуй[нсл]',
]


class ChatBot:
    BOT_USERNAME = "ModeratorBot"

    @staticmethod
    def get_bot_user():
        bot = User.query.filter_by(username=ChatBot.BOT_USERNAME).first()
        if not bot:
            from werkzeug.security import generate_password_hash
            import secrets
            bot = User(
                username=ChatBot.BOT_USERNAME,
                email='bot@modbot.system',
                password_hash=generate_password_hash(secrets.token_hex(32)),
                role='ADMIN',
                bio='🤖 Автоматический модератор чата',
                avatar='img/bot-avatar.png'
            )
            db.session.add(bot)
            db.session.commit()
        elif bot.avatar != 'img/bot-avatar.png':
            bot.avatar = 'img/bot-avatar.png'
            db.session.commit()
        return bot

    @staticmethod
    def check_toxicity(text):
        """Возвращает (is_toxic, matched_words)"""
        text_lower = text.lower()
        # Нормализация (убираем спецсимволы, замены типа а->@)
        normalized = re.sub(r'[^а-яёa-z0-9\s]', '', text_lower)
        normalized = normalized.replace('ё', 'е')

        matched = []
        for word in TOXIC_WORDS:
            if word.replace('ё', 'е') in normalized:
                matched.append(word)

        for pattern in TOXIC_PATTERNS:
            if re.search(pattern, text_lower):
                matched.append('[pattern]')

        return (len(matched) > 0, matched)

    @staticmethod
    def get_active_mute(user_id):
        """Возвращает активный мут или None"""
        return ChatMute.query.filter_by(user_id=user_id) \
            .filter(ChatMute.muted_until > datetime.utcnow()) \
            .order_by(ChatMute.muted_until.desc()).first()

    @staticmethod
    def mute_user(user_id, minutes=10, reason="Токсичное поведение"):
        mute = ChatMute(
            user_id=user_id,
            muted_until=datetime.utcnow() + timedelta(minutes=minutes),
            reason=reason
        )
        db.session.add(mute)
        db.session.commit()
        return mute

    @staticmethod
    def send_bot_message(room_id, text):
        bot = ChatBot.get_bot_user()
        msg = ChatMessage(
            room_id=room_id,
            user_id=bot.id,
            content=text,
            is_bot=True
        )
        db.session.add(msg)
        db.session.commit()
        return msg

    @staticmethod
    def process_message(user, room_id, text):
        """
        Главный метод. Возвращает dict:
        {'allowed': bool, 'message': str, 'muted': bool}
        """
        # 1. Проверка существующего мута
        mute = ChatBot.get_active_mute(user.id)
        if mute:
            remaining = int((mute.muted_until - datetime.utcnow()).total_seconds() / 60) + 1
            return {
                'allowed': False,
                'message': f'🔇 Вы заглушены ещё на ~{remaining} мин. Причина: {mute.reason}',
                'muted': True
            }

        # 2. Проверка токсичности
        is_toxic, matched = ChatBot.check_toxicity(text)
        if is_toxic:
            ChatBot.mute_user(
                user.id,
                minutes=10,
                reason=f"Токсичность: {', '.join(matched[:3])}"
            )
            ChatBot.send_bot_message(
                room_id,
                f"⚠️ Пользователь @{user.username} получил мут на 10 минут за токсичность."
            )
            return {
                'allowed': False,
                'message': '🚫 Сообщение заблокировано. Вы получили мут на 10 минут.',
                'muted': True
            }

        # 3. Слишком много заглавных (крик)
        letters = [c for c in text if c.isalpha()]
        if len(letters) > 8 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.75:
            return {
                'allowed': False,
                'message': '🔊 Не пишите КАПСОМ! Уменьшите количество заглавных букв.',
                'muted': False
            }

        # 4. Спам (одинаковые символы)
        if re.search(r'(.)\1{9,}', text):
            return {
                'allowed': False,
                'message': '🚫 Спам обнаружен.',
                'muted': False
            }

        return {'allowed': True, 'message': 'OK', 'muted': False}