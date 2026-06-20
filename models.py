from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ============================================
# СВЯЗУЮЩИЕ ТАБЛИЦЫ
# ============================================

manga_genres = db.Table('manga_genres',
    db.Column('manga_id', db.Integer, db.ForeignKey('manga.id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id'), primary_key=True)
)

manga_authors = db.Table('manga_authors',
    db.Column('manga_id', db.Integer, db.ForeignKey('manga.id'), primary_key=True),
    db.Column('author_id', db.Integer, db.ForeignKey('authors.id'), primary_key=True)
)

collection_items = db.Table('collection_items',
    db.Column('collection_id', db.Integer, db.ForeignKey('collections.id'), primary_key=True),
    db.Column('manga_id', db.Integer, db.ForeignKey('manga.id'), primary_key=True)
)

user_achievements = db.Table('user_achievements',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('achievement_id', db.Integer, db.ForeignKey('achievements.id'), primary_key=True)
)

follows = db.Table('follows',
    db.Column('follower_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('following_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

team_projects = db.Table('team_projects',
    db.Column('team_id', db.Integer, db.ForeignKey('translation_teams.id'), primary_key=True),
    db.Column('manga_id', db.Integer, db.ForeignKey('manga.id'), primary_key=True),
    db.Column('added_at', db.DateTime, default=datetime.utcnow)
)

# 🎨 Разблокированные пользователем рамки (для крафта/наград/доната)
user_unlocked_frames = db.Table('user_unlocked_frames',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('frame_id', db.Integer, db.ForeignKey('avatar_frames.id'), primary_key=True),
    db.Column('unlocked_at', db.DateTime, default=datetime.utcnow)
)

# 🖼️ Разблокированные баннеры
user_unlocked_banners = db.Table('user_unlocked_banners',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('banner_id', db.Integer, db.ForeignKey('profile_banners.id'), primary_key=True),
    db.Column('unlocked_at', db.DateTime, default=datetime.utcnow)
)

# 🎁 Инвентарь стикеров
user_stickers = db.Table('user_stickers',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('sticker_id', db.Integer, db.ForeignKey('stickers.id'), primary_key=True),
    db.Column('acquired_at', db.DateTime, default=datetime.utcnow)
)


# ============================================
# ПОЛЬЗОВАТЕЛИ
# ============================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar = db.Column(db.String(256))
    banner = db.Column(db.String(256))
    bio = db.Column(db.Text)
    role = db.Column(db.String(20), default='USER')  # USER, MODERATOR, ADMIN
    
    # ⚡ Премиум система
    is_premium = db.Column(db.Boolean, default=False)
    premium_until = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 🎨 Активная рамка аватарки
    active_frame_id = db.Column(db.Integer, db.ForeignKey('avatar_frames.id'), nullable=True)
    active_frame = db.relationship('AvatarFrame', foreign_keys=[active_frame_id])

    # 🖼️ Активный баннер профиля
    active_banner_id = db.Column(db.Integer, db.ForeignKey('profile_banners.id'), nullable=True)
    active_banner = db.relationship('ProfileBanner', foreign_keys=[active_banner_id])

    # Все разблокированные рамки
    unlocked_frames = db.relationship(
        'AvatarFrame',
        secondary=user_unlocked_frames,
        backref=db.backref('owners', lazy='dynamic'),
        lazy='dynamic'
    )

    # Все разблокированные баннеры
    unlocked_banners = db.relationship(
        'ProfileBanner',
        secondary=user_unlocked_banners,
        backref=db.backref('owners', lazy='dynamic'),
        lazy='dynamic'
    )

    # 🎁 Разблокированные стикеры
    stickers = db.relationship(
        'Sticker',
        secondary=user_stickers,
        backref=db.backref('owners', lazy='dynamic'),
        lazy='dynamic'
    )

    library = db.relationship('UserLibrary', backref='user', lazy='dynamic')
    reviews = db.relationship('Review', backref='user', lazy='dynamic')
    comments = db.relationship('Comment', backref='user', lazy='dynamic')
    collections = db.relationship('Collection', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    followed = db.relationship(
        'User', secondary=follows,
        primaryjoin=(follows.c.follower_id == id),
        secondaryjoin=(follows.c.following_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    # ===================== Хелперы =====================
    @property
    def is_admin(self):
        return (self.role or '').upper() == 'ADMIN'

    @property
    def is_moderator(self):
        return (self.role or '').upper() in ('MODERATOR', 'ADMIN')

    @property
    def is_banned(self):
        """Проверка активного бана"""
        ban = UserBan.query.filter_by(user_id=self.id, is_active=True).first()
        if not ban:
            return False
        if ban.banned_until and ban.banned_until < datetime.utcnow():
            ban.is_active = False
            db.session.commit()
            return False
        return True

    @property
    def active_ban(self):
        return UserBan.query.filter_by(user_id=self.id, is_active=True).first()

    def get_teams(self):
        owned = list(self.owned_teams)
        member_teams = [m.team for m in self.team_memberships]
        result = {t.id: t for t in owned + member_teams}
        return list(result.values())

    # 🎨 ===== Хелперы для рамок =====
    @property
    def frame_image(self):
        """Путь к картинке активной рамки (или None)."""
        return self.active_frame.image if self.active_frame else None

    def has_frame(self, frame):
        """Доступна ли пользователю данная рамка."""
        if frame is None:
            return False
        # Бесплатные доступны всем
        if not frame.is_premium:
            return True
        # Админы видят всё
        if self.is_admin:
            return True
        # Проверяем разблокированные
        return self.unlocked_frames.filter(AvatarFrame.id == frame.id).first() is not None

    def unlock_frame(self, frame):
        """Разблокировать рамку для пользователя."""
        if frame and not self.unlocked_frames.filter(AvatarFrame.id == frame.id).first():
            self.unlocked_frames.append(frame)
            return True
        return False

    def has_banner(self, banner):
        """Доступен ли пользователю данный баннер."""
        if banner is None:
            return False
        if not banner.is_premium:
            return True
        if self.is_admin:
            return True
        return self.unlocked_banners.filter(ProfileBanner.id == banner.id).first() is not None

    def unlock_banner(self, banner):
        """Разблокировать баннер для пользователя."""
        if banner and not self.unlocked_banners.filter(ProfileBanner.id == banner.id).first():
            self.unlocked_banners.append(banner)
            return True
        return False


# ============================================
# 🎨 РАМКИ ДЛЯ АВАТАРОК
# ============================================

class AvatarFrame(db.Model):
    """Декоративные рамки для аватарок пользователей"""
    __tablename__ = 'avatar_frames'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)          # blue_crystal
    name = db.Column(db.String(128), nullable=False)                      # "Ледяной кристалл"
    description = db.Column(db.String(255), nullable=True)
    image = db.Column(db.String(256), nullable=False)                     # путь от static/, напр. "img/frames/blue_crystal.png"

    rarity = db.Column(db.String(32), default='common', nullable=False)   # common, rare, epic, legendary, mythic
    is_premium = db.Column(db.Boolean, default=False, nullable=False)     # True = нужно разблокировать
    price = db.Column(db.Integer, default=0)                              # цена (если будет валюта)
    is_active = db.Column(db.Boolean, default=True, nullable=False)       # показывать в магазине

    # 🎨 CSS-класс для цвета свечения вокруг рамки
    # Доступные: glow-blue, glow-red, glow-purple, glow-gold, glow-green, glow-pink, glow-fire, glow-rainbow, glow-pulse-red
    glow_class = db.Column(db.String(32), default='glow-blue')

    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def rarity_label(self):
        return {
            'common':    'Обычная',
            'rare':      'Редкая',
            'epic':      'Эпическая',
            'legendary': 'Легендарная',
            'mythic':    'Мифическая',
        }.get(self.rarity, self.rarity)

    @property
    def rarity_color_class(self):
        """Tailwind-классы для бейджа редкости."""
        return {
            'common':    'bg-gray-700 text-gray-300',
            'rare':      'bg-blue-600/80 text-white',
            'epic':      'bg-purple-600/80 text-white',
            'legendary': 'bg-gradient-to-r from-yellow-400 to-orange-500 text-black',
            'mythic':    'bg-gradient-to-r from-pink-500 to-purple-600 text-white',
        }.get(self.rarity, 'bg-gray-700 text-gray-300')

    @property
    def glow_class_safe(self):
        """Безопасный геттер свечения (если null — дефолт)."""
        return self.glow_class or 'glow-blue'


# ============================================
# 🖼️ БАННЕРЫ ПРОФИЛЯ
# ============================================

class ProfileBanner(db.Model):
    """Декоративные баннеры для шапки профиля пользователя"""
    __tablename__ = 'profile_banners'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)          # gothic_cross
    name = db.Column(db.String(128), nullable=False)                      # "Готический крест"
    description = db.Column(db.String(255), nullable=True)
    image = db.Column(db.String(256), nullable=False)                     # путь от static/

    rarity = db.Column(db.String(32), default='common', nullable=False)   # common, rare, epic, legendary, mythic
    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    price = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def rarity_label(self):
        return {
            'common':    'Обычная',
            'rare':      'Редкая',
            'epic':      'Эпическая',
            'legendary': 'Легендарная',
            'mythic':    'Мифическая',
        }.get(self.rarity, self.rarity)

    @property
    def rarity_color_class(self):
        return {
            'common':    'bg-gray-700 text-gray-300',
            'rare':      'bg-blue-600/80 text-white',
            'epic':      'bg-purple-600/80 text-white',
            'legendary': 'bg-gradient-to-r from-yellow-400 to-orange-500 text-black',
            'mythic':    'bg-gradient-to-r from-pink-500 to-purple-600 text-white',
        }.get(self.rarity, 'bg-gray-700 text-gray-300')


# ============================================
# 🎁 СТИКЕРЫ
# ============================================

class Sticker(db.Model):
    __tablename__ = 'stickers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(256), nullable=False) # e.g. "img/stickers/cat1.png"
    pack_name = db.Column(db.String(100), default='Леди Безе')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
# ============================================
# МАНГА
# ============================================

class Manga(db.Model):
    __tablename__ = 'manga'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    original_title = db.Column(db.String(200))
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(256))
    release_year = db.Column(db.Integer)
    status = db.Column(db.String(50))
    rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    comments_count = db.Column(db.Integer, default=0)
    chapters_count = db.Column(db.Integer, default=0)
    volumes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    genres = db.relationship('Genre', secondary=manga_genres, backref=db.backref('mangas', lazy='dynamic'))
    authors = db.relationship('Author', secondary=manga_authors, backref=db.backref('mangas', lazy='dynamic'))


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Author(db.Model):
    __tablename__ = 'authors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(256))


class MangaRating(db.Model):
    __tablename__ = 'manga_ratings'
    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('manga_id', 'user_id', name='uq_manga_rating_user'),
    )

    manga = db.relationship('Manga', backref=db.backref('ratings', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('manga_ratings', lazy='dynamic'))


# ============================================
# БИБЛИОТЕКА / ОТЗЫВЫ / КОММЕНТАРИИ
# ============================================

class UserLibrary(db.Model):
    __tablename__ = 'user_library'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    reading_status = db.Column(db.String(50), nullable=False, default='PLAN_TO_READ')
    current_chapter = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer)
    favorite = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    manga = db.relationship('Manga', backref=db.backref('library_entries', lazy='dynamic'))


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manga = db.relationship('Manga', backref=db.backref('reviews', lazy='dynamic'))


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manga = db.relationship('Manga', backref=db.backref('comments', lazy='dynamic'))

    @property
    def author(self):
        return self.user


# ============================================
# КОЛЛЕКЦИИ / ДОСТИЖЕНИЯ / УВЕДОМЛЕНИЯ
# ============================================

class Collection(db.Model):
    __tablename__ = 'collections'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    items = db.relationship('Manga', secondary=collection_items, backref=db.backref('collections', lazy='dynamic'))


class Achievement(db.Model):
    __tablename__ = 'achievements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(256))

    users = db.relationship('User', secondary=user_achievements, backref=db.backref('achievements', lazy='dynamic'))


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================

class HeroBlock(db.Model):
    __tablename__ = 'hero_blocks'
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, unique=True, nullable=False)
    image_filename = db.Column(db.String(256), nullable=False)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manga = db.relationship('Manga', backref='hero_blocks')


# ============================================
# КОМАНДЫ ПЕРЕВОДА
# ============================================

class TeamApplication(db.Model):
    __tablename__ = 'team_applications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    short_description = db.Column(db.String(200), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    languages = db.Column(db.String(300), nullable=False)
    required_roles = db.Column(db.String(300), nullable=False)
    logo = db.Column(db.String(256))
    reason = db.Column(db.Text, nullable=False)
    additional_info = db.Column(db.Text)

    status = db.Column(db.String(20), default='PENDING', nullable=False)
    rejection_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    user = db.relationship('User', foreign_keys=[user_id], backref='team_applications')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])


class TranslationTeam(db.Model):
    __tablename__ = 'translation_teams'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    short_description = db.Column(db.String(200))
    full_description = db.Column(db.Text)
    languages = db.Column(db.String(300))
    logo = db.Column(db.String(256))
    banner = db.Column(db.String(256))

    is_recruiting = db.Column(db.Boolean, default=True)
    recruitment_text = db.Column(db.Text)
    required_roles = db.Column(db.String(300))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='owned_teams')
    members = db.relationship('TeamMember', backref='team', cascade='all, delete-orphan', lazy='dynamic')
    projects = db.relationship('Manga', secondary=team_projects, backref='translation_teams')
    invitations = db.relationship('TeamInvitation', backref='team', cascade='all, delete-orphan', lazy='dynamic')

    def has_member(self, user):
        if user is None or not getattr(user, 'is_authenticated', False):
            return False
        if self.owner_id == user.id:
            return True
        return self.members.filter_by(user_id=user.id).first() is not None


class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('translation_teams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    role = db.Column(db.String(50), default='MEMBER')
    role_label = db.Column(db.String(100))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='team_memberships')

    __table_args__ = (db.UniqueConstraint('team_id', 'user_id', name='unique_team_member'),)


class TeamInvitation(db.Model):
    __tablename__ = 'team_invitations'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('translation_teams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    role = db.Column(db.String(50), default='MEMBER')
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='team_invitations_received')
    invited_by = db.relationship('User', foreign_keys=[invited_by_id])


# ============================================
# ГЛАВЫ И ФРЕЙМЫ
# ============================================

class Chapter(db.Model):
    __tablename__ = 'chapters'
    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, db.ForeignKey('manga.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('translation_teams.id'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    volume = db.Column(db.Integer, default=1, nullable=False)
    number = db.Column(db.Float, nullable=False)
    title = db.Column(db.String(200))
    is_paid = db.Column(db.Boolean, default=False) # Платная ли глава

    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manga = db.relationship('Manga', backref=db.backref(
        'chapters', lazy='dynamic', cascade='all, delete-orphan',
        order_by='Chapter.number.desc()'))
    team = db.relationship('TranslationTeam', backref=db.backref(
        'chapters', lazy='dynamic', cascade='all, delete-orphan'))
    uploader = db.relationship('User', backref='uploaded_chapters')

    frames = db.relationship('ChapterFrame', backref='chapter',
                             cascade='all, delete-orphan',
                             order_by='ChapterFrame.order',
                             lazy='select')

    __table_args__ = (
        db.UniqueConstraint('manga_id', 'team_id', 'number',
                            name='uq_chapter_manga_team_number'),
    )

    @property
    def display_number(self):
        return str(int(self.number)) if self.number.is_integer() else str(self.number)

    @property
    def frames_count(self):
        return len(self.frames)


class ChapterFrame(db.Model):
    __tablename__ = 'chapter_frames'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=0)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================
# ФОРУМ
# ============================================

class ForumTopic(db.Model):
    __tablename__ = 'forum_topics'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    is_closed = db.Column(db.Boolean, default=False)

    author = db.relationship('User', backref='forum_topics')
    posts = db.relationship('ForumPost', backref='topic', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def posts_count(self):
        return self.posts.count()

    @property
    def last_post(self):
        return self.posts.order_by(ForumPost.created_at.desc()).first()


class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topics.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', backref='forum_posts')


# ============================================
# 🛡️ МОДЕРАЦИЯ
# ============================================

class ModerationLog(db.Model):
    __tablename__ = 'moderation_logs'
    id = db.Column(db.Integer, primary_key=True)
    moderator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    moderator = db.relationship('User', backref='moderation_actions', foreign_keys=[moderator_id])


class UserBan(db.Model):
    __tablename__ = 'user_bans'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    banned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    banned_until = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='ban_history')
    banned_by = db.relationship('User', foreign_keys=[banned_by_id])

# ============ ЧАТ ============

class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    room_type = db.Column(db.String(20), default='general')  # 'general' / 'moderators'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='room', lazy='dynamic',
                               cascade='all, delete-orphan')


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('chat_rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_bot = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='chat_messages')


class ChatMute(db.Model):
    __tablename__ = 'chat_mutes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    muted_until = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='mutes')