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
    role = db.Column(db.String(20), default='USER')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    # Удобные хелперы
    @property
    def is_admin(self):
        return (self.role or '').upper() == 'ADMIN'

    def get_teams(self):
        """Команды, в которых пользователь состоит (как участник или владелец)."""
        owned = list(self.owned_teams)
        member_teams = [m.team for m in self.team_memberships]
        # Уникальные
        result = {t.id: t for t in owned + member_teams}
        return list(result.values())


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
    chapters_count = db.Column(db.Integer, default=0)
    volumes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    genres = db.relationship('Genre', secondary=manga_genres, backref=db.backref('mangas', lazy='dynamic'))
    authors = db.relationship('Author', secondary=manga_authors, backref=db.backref('mangas', lazy='dynamic'))

    # chapters добавляется через backref в модели Chapter


class Genre(db.Model):
    __tablename__ = 'genres'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Author(db.Model):
    __tablename__ = 'authors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(256))


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
        """Состоит ли пользователь в команде (включая владельца)."""
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
    number = db.Column(db.Float, nullable=False)   # поддержка 1, 1.5, 2 и т.д.
    title = db.Column(db.String(200))

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
        # 12.0 -> "12", 12.5 -> "12.5"
        return str(int(self.number)) if self.number.is_integer() else str(self.number)

    @property
    def frames_count(self):
        return len(self.frames)


class ChapterFrame(db.Model):
    __tablename__ = 'chapter_frames'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    image_path = db.Column(db.String(500), nullable=False)  # путь относительно /static/
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