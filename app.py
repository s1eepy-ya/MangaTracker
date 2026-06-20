import os
import re
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, inspect, text
from models import (db, User, Genre, Manga, Comment, UserLibrary, HeroBlock,
                    Notification, TeamApplication, TranslationTeam,
                    TeamMember, TeamInvitation, ForumTopic, ForumPost,
                    Chapter, ChapterFrame, ModerationLog, UserBan,
                    AvatarFrame, ProfileBanner, ChatRoom, ChatMessage, ChatMute, MangaRating)
from chat_bot import ChatBot

# ============ КОНФИГ ============
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join('static', 'img')
COVERS_FOLDER = os.path.join('static', 'img', 'covers')
AVATARS_FOLDER = os.path.join('static', 'img', 'avatars')
BANNERS_FOLDER = os.path.join('static', 'img', 'banners')
TEAMS_LOGOS_FOLDER = os.path.join('static', 'img', 'teams', 'logos')
TEAMS_BANNERS_FOLDER = os.path.join('static', 'img', 'teams', 'banners')
CHAPTERS_FOLDER = os.path.join('static', 'img', 'chapters')
FRAMES_FOLDER = os.path.join('static', 'img', 'frames')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_CHAPTER_UPLOAD = 300 * 1024 * 1024


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Требуется авторизация', 'error')
            return redirect(url_for('login'))
        if current_user.role != 'ADMIN':
            flash('У вас нет прав администратора!', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Требуется авторизация', 'error')
            return redirect(url_for('login'))
        if current_user.role not in ('MODERATOR', 'ADMIN'):
            flash('Только для модераторов!', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def log_moderation_action(action, target_type=None, target_id=None, reason=None):
    try:
        log = ModerationLog(
            moderator_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'⚠️ Ошибка логирования: {e}')


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:120] or 'team'


def create_notification(user_id, notif_type, content):
    notif = Notification(user_id=user_id, type=notif_type, content=content)
    db.session.add(notif)
    db.session.commit()


def user_in_team(user, team):
    if not user or not user.is_authenticated:
        return False
    if team.owner_id == user.id:
        return True
    return TeamMember.query.filter_by(team_id=team.id, user_id=user.id).first() is not None


def recalc_chapters_count(manga):
    cnt = db.session.query(func.count(func.distinct(Chapter.number))).filter(
        Chapter.manga_id == manga.id
    ).scalar() or 0
    manga.chapters_count = cnt


def get_database_uri():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        return db_url
    return f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"


def seed_default_frames():
    """Создаёт стартовые рамки, если их ещё нет в БД."""
    DEFAULT_FRAMES = [
        {
            'code': 'blue_crystal',
            'name': 'Ледяной кристалл',
            'description': 'Магическая рамка с синими кристаллами и цветами',
            'image': 'img/frames/blue_crystal.png',
            'rarity': 'epic',
            'is_premium': False,
            'sort_order': 10,
            'glow_class': 'glow-blue',
        },
        {
            'code': 'dark_rose',
            'name': 'Тёмная роза',
            'description': 'Загадочная рамка с тёмными розами и готическим узором',
            'image': 'img/frames/dark_rose.png',
            'rarity': 'legendary',
            'is_premium': False,
            'sort_order': 20,
            'glow_class': 'glow-red',
        },
        {
            'code': 'fire_dragon',
            'name': 'Огненный дракон',
            'description': 'Мифическая рамка с пылающим огнём и чешуёй дракона',
            'image': 'img/frames/fire_dragon_v2.png',
            'rarity': 'mythic',
            'is_premium': True,
            'sort_order': 30,
            'glow_class': 'glow-orange',
        },
        {
            'code': 'golden_crown',
            'name': 'Золотая корона',
            'description': 'Королевская золотая рамка с драгоценными камнями',
            'image': 'img/frames/golden_crown_v2.png',
            'rarity': 'legendary',
            'is_premium': False,
            'sort_order': 40,
            'glow_class': 'glow-yellow',
        },
        {
            'code': 'neon_cyberpunk',
            'name': 'Неоновый киберпанк',
            'description': 'Футуристичная неоновая рамка с кибер-элементами',
            'image': 'img/frames/neon_cyberpunk_v2.png',
            'rarity': 'epic',
            'is_premium': False,
            'sort_order': 50,
            'glow_class': 'glow-pink',
        },
        {
            'code': 'gothic_cross',
            'name': 'Готический крест',
            'description': 'Мрачная готическая рамка с розами, идеально подходящая к баннеру',
            'image': 'img/frames/gothic_cross_frame.png',
            'rarity': 'legendary',
            'is_premium': False,
            'sort_order': 60,
            'glow_class': 'glow-purple',
        },
    ]
    try:
        for data in DEFAULT_FRAMES:
            existing = AvatarFrame.query.filter_by(code=data['code']).first()
            if existing:
                if not existing.glow_class:
                    existing.glow_class = data.get('glow_class', 'glow-blue')
            else:
                db.session.add(AvatarFrame(**data))
        db.session.commit()
        print('✅ Дефолтные рамки проверены/созданы')
    except Exception as e:
        db.session.rollback()
        print(f'⚠️ Сидинг рамок пропущен: {e}')

def seed_default_banners():
    """Создаёт стартовые баннеры."""
    from models import ProfileBanner
    DEFAULT_BANNERS = [
        {
            'code': 'gothic_cross',
            'name': 'Готический крест',
            'description': 'Мрачный готический баннер с розами и крестом',
            'image': 'img/banners/gothic_cross.png',
            'rarity': 'legendary',
            'is_premium': False,
            'sort_order': 10,
        },
        {
            'code': 'dark_rose',
            'name': 'Тёмная роза',
            'description': 'Идеально сочетается с рамкой Тёмная роза: глубокий багровый градиент и розы',
            'image': 'img/banners/dark_rose.png',
            'rarity': 'epic',
            'is_premium': False,
            'sort_order': 20,
        },
    ]
    try:
        for data in DEFAULT_BANNERS:
            existing = ProfileBanner.query.filter_by(code=data['code']).first()
            if not existing:
                db.session.add(ProfileBanner(**data))
        db.session.commit()
        print('✅ Дефолтные баннеры проверены/созданы')
    except Exception as e:
        db.session.rollback()
        print(f'⚠️ Сидинг баннеров пропущен: {e}')

def seed_stickers():
    try:
        from models import Sticker
        if Sticker.query.count() == 0:
            s1 = Sticker(name='Леди Безе 1', image_path='img/stickers/cat1.png')
            s2 = Sticker(name='Леди Безе 2', image_path='img/stickers/cat2.png')
            s3 = Sticker(name='Леди Безе 3', image_path='img/stickers/cat3.png')
            s4 = Sticker(name='Леди Безе 4', image_path='img/stickers/cat4.png')
            db.session.add_all([s1, s2, s3, s4])
            db.session.commit()
            print('✅ Стикеры загружены')
    except Exception as e:
        db.session.rollback()
        print(f'⚠️ Ошибка стикеров: {e}')


def auto_update_database(app):
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            model_tables = set(db.metadata.tables.keys())
            new_tables = model_tables - existing_tables

            if new_tables:
                print(f'📦 Создаются новые таблицы: {", ".join(new_tables)}')

            db.create_all()

            # 🔧 АВТО-МИГРАЦИЯ users
            inspector = inspect(db.engine)
            existing_columns = {c['name'] for c in inspector.get_columns('users')}

            user_migrations = [
                ('active_frame_id', 'INTEGER REFERENCES avatar_frames(id)'),
                ('active_banner_id', 'INTEGER REFERENCES profile_banners(id)'),
                ('is_premium', 'BOOLEAN DEFAULT FALSE'),
                ('premium_until', 'DATETIME'),
            ]

            for col_name, col_def in user_migrations:
                if col_name not in existing_columns:
                    try:
                        with db.engine.connect() as conn:
                            conn.execute(text(
                                f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"
                            ))
                            conn.commit()
                        print(f'✅ Добавлена колонка users.{col_name}')
                    except Exception as e:
                        print(f'⚠️ Не удалось добавить колонку users.{col_name}: {e}')

            # 🔧 АВТО-МИГРАЦИЯ avatar_frames
            if 'avatar_frames' in inspector.get_table_names():
                frame_columns = {c['name'] for c in inspector.get_columns('avatar_frames')}
                frame_migrations = [
                    ('glow_class', "VARCHAR(32) DEFAULT 'glow-blue'"),
                ]
                for col_name, col_def in frame_migrations:
                    if col_name not in frame_columns:
                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text(
                                    f"ALTER TABLE avatar_frames ADD COLUMN {col_name} {col_def}"
                                ))
                                conn.commit()
                            print(f'✅ Добавлена колонка avatar_frames.{col_name}')
                        except Exception as e:
                            print(f'⚠️ Не удалось добавить колонку avatar_frames.{col_name}: {e}')

            # 🔧 АВТО-МИГРАЦИЯ chapters
            if 'chapters' in inspector.get_table_names():
                chapter_columns = {c['name'] for c in inspector.get_columns('chapters')}
                chapter_migrations = [
                    ('is_paid', "BOOLEAN DEFAULT FALSE"),
                ]
                for col_name, col_def in chapter_migrations:
                    if col_name not in chapter_columns:
                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text(
                                    f"ALTER TABLE chapters ADD COLUMN {col_name} {col_def}"
                                ))
                                conn.commit()
                            print(f'✅ Добавлена колонка chapters.{col_name}')
                        except Exception as e:
                            print(f'⚠️ Не удалось добавить колонку chapters.{col_name}: {e}')

            # 🔧 АВТО-МИГРАЦИЯ manga
            if 'manga' in inspector.get_table_names():
                manga_columns = {c['name'] for c in inspector.get_columns('manga')}
                manga_migrations = [
                    ('views', "INTEGER DEFAULT 0"),
                    ('comments_count', "INTEGER DEFAULT 0"),
                    ('rating_count', "INTEGER DEFAULT 0"),
                ]
                for col_name, col_def in manga_migrations:
                    if col_name not in manga_columns:
                        try:
                            with db.engine.connect() as conn:
                                conn.execute(text(
                                    f"ALTER TABLE manga ADD COLUMN {col_name} {col_def}"
                                ))
                                conn.commit()
                            print(f'✅ Добавлена колонка manga.{col_name}')
                        except Exception as e:
                            print(f'⚠️ Не удалось добавить колонку manga.{col_name}: {e}')

            print('✅ База данных синхронизирована')

            if Manga.query.count() == 0:
                try:
                    from seed import seed_database
                    seed_database()
                    print('✅ База данных заполнена начальными данными')
                except Exception as e:
                    print(f'⚠️ Сидинг пропущен: {e}')

            # 🎨 Заполняем стартовые рамки
            seed_default_frames()

            # 🖼️ Заполняем стартовые баннеры
            seed_default_banners()

            # 🎁 Заполняем стикеры
            seed_stickers()

            # 💬 Создаём комнаты чата
            try:
                if not ChatRoom.query.filter_by(room_type='general').first():
                    db.session.add(ChatRoom(name='Общий чат', room_type='general'))
                if not ChatRoom.query.filter_by(room_type='moderators').first():
                    db.session.add(ChatRoom(name='Чат модераторов', room_type='moderators'))
                db.session.commit()
                print('✅ Комнаты чата готовы')
            except Exception as e:
                db.session.rollback()
                print(f'⚠️ Ошибка создания комнат чата: {e}')

        except Exception as e:
            print(f'❌ Ошибка инициализации БД: {e}')


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-it')
    app.config['MAX_CONTENT_LENGTH'] = MAX_CHAPTER_UPLOAD

    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    for folder in [UPLOAD_FOLDER, COVERS_FOLDER, AVATARS_FOLDER, BANNERS_FOLDER,
                   TEAMS_LOGOS_FOLDER, TEAMS_BANNERS_FOLDER, CHAPTERS_FOLDER,
                   FRAMES_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ===================== ГЛАВНАЯ =====================
    @app.route('/')
    def index():
        popular_mangas = Manga.query.order_by(Manga.views.desc(), Manga.comments_count.desc(), Manga.rating.desc()).limit(8).all()
        
        # Новинки за последние 7 дней (с fallback на просто новые, если их мало)
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_mangas = Manga.query.filter(Manga.created_at >= week_ago).order_by(Manga.views.desc()).limit(6).all()
        if len(new_mangas) < 6:
            additional = Manga.query.filter(Manga.id.notin_([m.id for m in new_mangas])).order_by(Manga.created_at.desc()).limit(6 - len(new_mangas)).all()
            new_mangas.extend(additional)

        genres = Genre.query.order_by(Genre.name).all()

        hero_blocks = HeroBlock.query.order_by(HeroBlock.position).all()
        if not hero_blocks:
            for i in range(1, 7):
                ext = 'jpg' if i in [1, 2] else 'png'
                default_block = HeroBlock(
                    position=i,
                    image_filename=f'block{i}.{ext}',
                    manga_id=i if Manga.query.get(i) else None
                )
                db.session.add(default_block)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f'⚠️ Не удалось создать hero-блоки: {e}')
            hero_blocks = HeroBlock.query.order_by(HeroBlock.position).all()

        stats = {
            'manga_count': db.session.query(func.count(Manga.id)).scalar() or 0,
            'users_count': db.session.query(func.count(User.id)).scalar() or 0,
            'chapters_count': db.session.query(func.coalesce(func.sum(Manga.chapters_count), 0)).scalar() or 0,
            'genres_count': db.session.query(func.count(Genre.id)).scalar() or 0
        }

        return render_template('index.html',
                               popular_mangas=popular_mangas,
                               new_mangas=new_mangas,
                               genres=genres,
                               stats=stats,
                               hero_blocks=hero_blocks)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')

            user_exists = User.query.filter((User.username == username) | (User.email == email)).first()
            if user_exists:
                flash('Имя пользователя или почта уже заняты', 'error')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password, method='scrypt')
            new_user = User(username=username, email=email, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            # Выдаем уведомление со стикерами
            create_notification(
                new_user.id,
                'GIFT_STICKERS',
                'Вам доступен набор стикеров "Леди Безе"! Нажмите "Принять", чтобы распаковать подарок 🎁'
            )

            flash('Вы успешно зарегистрировались!', 'success')
            login_user(new_user)
            return redirect(url_for('index'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password_hash, password):
                flash('Неверное имя пользователя или пароль', 'error')
                return redirect(url_for('login'))

            if user.is_banned:
                ban = user.active_ban
                if ban.banned_until:
                    msg = f'🚫 Вы забанены до {ban.banned_until.strftime("%d.%m.%Y %H:%M")}. Причина: {ban.reason}'
                else:
                    msg = f'🚫 Вы забанены навсегда. Причина: {ban.reason}'
                flash(msg, 'error')
                return redirect(url_for('login'))

            login_user(user)
            return redirect(url_for('index'))

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'success')
        return redirect(url_for('index'))

    @app.route('/api/accept_gift/<int:notif_id>', methods=['POST'])
    @login_required
    def accept_gift(notif_id):
        notif = Notification.query.get_or_404(notif_id)
        if notif.user_id != current_user.id or notif.type != 'GIFT_STICKERS':
            return jsonify({'error': 'Недоступно'}), 403
            
        if not notif.is_read:
            notif.is_read = True
            from models import Sticker
            stickers = Sticker.query.all()
            for s in stickers:
                if s not in current_user.stickers:
                    current_user.stickers.append(s)
            db.session.commit()
            return jsonify({'success': True, 'stickers': [s.image_path for s in stickers]})
        
        return jsonify({'error': 'Подарок уже принят'}), 400

    @app.route('/api/my_stickers')
    @login_required
    def my_stickers():
        stickers = current_user.stickers.all()
        
        # Выдаем стикеры старым пользователям ретроактивно
        if not stickers:
            from models import Sticker
            all_stickers = Sticker.query.all()
            if all_stickers:
                for s in all_stickers:
                    current_user.stickers.append(s)
                db.session.commit()
                stickers = all_stickers
                
        return jsonify([{
            'id': s.id,
            'name': s.name,
            'image_path': url_for('static', filename=s.image_path),
            'pack_name': s.pack_name
        } for s in stickers])

    @app.route('/catalog')
    def catalog():
        search_query = request.args.get('search', '')
        selected_genre = request.args.get('genre', '')

        manga_query = Manga.query
        if search_query:
            manga_query = manga_query.filter(
                Manga.title.ilike(f"%{search_query}%") |
                Manga.original_title.ilike(f"%{search_query}%")
            )
        if selected_genre:
            manga_query = manga_query.filter(Manga.genres.any(id=selected_genre))

        mangas = manga_query.order_by(Manga.rating.desc()).all()
        genres = Genre.query.all()
        return render_template('catalog.html',
                               mangas=mangas, genres=genres,
                               search_query=search_query,
                               selected_genre=selected_genre)

    @app.route('/manga/<int:manga_id>')
    def manga_detail(manga_id):
        manga = Manga.query.get_or_404(manga_id)
        manga.views = (manga.views or 0) + 1
        db.session.commit()
        
        library_entry = None
        user_rating = None
        if current_user.is_authenticated:
            library_entry = UserLibrary.query.filter_by(
                user_id=current_user.id, manga_id=manga_id
            ).first()
            rating_entry = MangaRating.query.filter_by(manga_id=manga_id, user_id=current_user.id).first()
            if rating_entry:
                user_rating = rating_entry.score

        comments = Comment.query.filter_by(manga_id=manga_id).order_by(Comment.created_at.desc()).all()

        chapters = Chapter.query.filter_by(manga_id=manga_id) \
            .order_by(Chapter.volume.desc(), Chapter.number.desc()).all()

        user_teams_for_upload = []
        if current_user.is_authenticated:
            owned = TranslationTeam.query.filter_by(owner_id=current_user.id).all()
            member_links = TeamMember.query.filter_by(user_id=current_user.id).all()
            member_teams = [m.team for m in member_links]
            seen = set()
            all_user_teams = []
            for t in owned + member_teams:
                if t.id not in seen:
                    seen.add(t.id)
                    all_user_teams.append(t)
            user_teams_for_upload = [t for t in all_user_teams if manga in t.projects]

        return render_template('manga.html',
                               manga=manga,
                               library_entry=library_entry,
                               user_rating=user_rating,
                               comments=comments,
                               chapters=chapters,
                               user_teams_for_upload=user_teams_for_upload)

    @app.route('/manga/<int:manga_id>/update_library', methods=['POST'])
    @login_required
    def update_library(manga_id):
        status = request.form.get('status')
        entry = UserLibrary.query.filter_by(
            user_id=current_user.id, manga_id=manga_id
        ).first()

        if status == 'NONE':
            if entry:
                db.session.delete(entry)
        else:
            if not entry:
                entry = UserLibrary(user_id=current_user.id, manga_id=manga_id)
                db.session.add(entry)
            entry.reading_status = status

        db.session.commit()
        flash('Статус в библиотеке успешно обновлен!', 'success')
        return redirect(url_for('manga_detail', manga_id=manga_id))

    @app.route('/manga/<int:manga_id>/add_comment', methods=['POST'])
    @login_required
    def add_comment(manga_id):
        if current_user.is_banned:
            flash('Забаненные пользователи не могут оставлять комментарии', 'error')
            return redirect(url_for('manga_detail', manga_id=manga_id))

        content = request.form.get('comment')
        if content:
            new_comment = Comment(
                user_id=current_user.id, manga_id=manga_id, content=content
            )
            db.session.add(new_comment)
            manga = Manga.query.get(manga_id)
            if manga:
                manga.comments_count = (manga.comments_count or 0) + 1
            db.session.commit()
            flash('Комментарий опубликован!', 'success')
        return redirect(url_for('manga_detail', manga_id=manga_id))

    @app.route('/api/manga/<int:manga_id>/rate', methods=['POST'])
    @login_required
    def rate_manga(manga_id):
        data = request.get_json()
        if not data or 'score' not in data:
            return jsonify({'success': False, 'error': 'Не указана оценка'}), 400
        
        try:
            score = int(data['score'])
            if score < 1 or score > 10:
                return jsonify({'success': False, 'error': 'Оценка должна быть от 1 до 10'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Неверный формат оценки'}), 400

        manga = Manga.query.get_or_404(manga_id)
        rating_entry = MangaRating.query.filter_by(manga_id=manga_id, user_id=current_user.id).first()

        if rating_entry:
            rating_entry.score = score
        else:
            rating_entry = MangaRating(manga_id=manga_id, user_id=current_user.id, score=score)
            db.session.add(rating_entry)
            manga.rating_count = (manga.rating_count or 0) + 1

        db.session.flush()

        # Recalculate average rating
        avg_rating = db.session.query(func.avg(MangaRating.score)).filter_by(manga_id=manga_id).scalar()
        manga.rating = float(avg_rating) if avg_rating else 0.0
        
        db.session.commit()

        return jsonify({
            'success': True,
            'new_rating': round(manga.rating, 1),
            'rating_count': manga.rating_count
        })

    @app.route('/teams/<slug>/manga/<int:manga_id>/chapters/add',
               methods=['GET', 'POST'])
    @login_required
    def chapter_add(slug, manga_id):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()
        manga = Manga.query.get_or_404(manga_id)

        if not user_in_team(current_user, team) and current_user.role != 'ADMIN':
            flash('Только участники команды могут загружать главы', 'error')
            return redirect(url_for('manga_detail', manga_id=manga_id))

        if manga not in team.projects:
            flash(f'Манга «{manga.title}» не относится к проектам команды «{team.name}». '
                  'Сначала добавьте её в проекты.', 'error')
            return redirect(url_for('team_detail', slug=slug))

        if request.method == 'POST':
            try:
                raw_number = request.form.get('number', '').strip().replace(',', '.')
                if not raw_number:
                    flash('Укажите номер главы', 'error')
                    return redirect(request.url)
                number = float(raw_number)
            except ValueError:
                flash('Некорректный номер главы (пример: 12 или 12.5)', 'error')
                return redirect(request.url)

            try:
                volume = int(request.form.get('volume') or 1)
            except ValueError:
                volume = 1

            title = (request.form.get('title') or '').strip() or None

            exists = Chapter.query.filter_by(
                manga_id=manga.id, team_id=team.id, number=number
            ).first()
            if exists:
                flash(f'Глава {number} уже загружена этой командой', 'error')
                return redirect(request.url)

            files = request.files.getlist('frames')
            files = [f for f in files if f and f.filename]
            if not files:
                flash('Загрузите хотя бы один фрейм (изображение)', 'error')
                return redirect(request.url)

            is_paid_val = request.form.get('is_paid') == 'on'

            chapter = Chapter(
                manga_id=manga.id,
                team_id=team.id,
                uploader_id=current_user.id,
                volume=volume,
                number=number,
                title=title,
                is_paid=is_paid_val
            )
            db.session.add(chapter)
            db.session.flush()

            rel_dir = f'chapters/{manga.id}/{team.id}/{chapter.id}'
            abs_dir = os.path.join('static', 'img', rel_dir)
            os.makedirs(abs_dir, exist_ok=True)

            saved = 0
            for idx, f in enumerate(files):
                if not allowed_file(f.filename):
                    continue
                ext = f.filename.rsplit('.', 1)[1].lower()
                unique_name = f'{idx:04d}_{uuid.uuid4().hex[:8]}.{ext}'
                abs_path = os.path.join(abs_dir, unique_name)
                f.save(abs_path)

                frame = ChapterFrame(
                    chapter_id=chapter.id,
                    image_path=f'img/{rel_dir}/{unique_name}',
                    order=idx
                )
                db.session.add(frame)
                saved += 1

            if saved == 0:
                db.session.rollback()
                flash('Не удалось сохранить ни одного фрейма (проверьте формат файлов)', 'error')
                return redirect(request.url)

            recalc_chapters_count(manga)
            if volume > (manga.volumes_count or 0):
                manga.volumes_count = volume

            db.session.commit()
            flash(f'Глава {chapter.display_number} успешно загружена ({saved} фреймов)', 'success')
            return redirect(url_for('manga_detail', manga_id=manga.id))

        return render_template('chapter_add.html', team=team, manga=manga)

    @app.route('/manga/<int:manga_id>/chapter/<int:chapter_id>')
    def chapter_read(manga_id, chapter_id):
        chapter = Chapter.query.get_or_404(chapter_id)
        if chapter.manga_id != manga_id:
            abort(404)

        chapter.views = (chapter.views or 0) + 1
        db.session.commit()

        prev_ch = Chapter.query.filter(
            Chapter.manga_id == manga_id,
            Chapter.team_id == chapter.team_id,
            Chapter.number < chapter.number
        ).order_by(Chapter.number.desc()).first()

        next_ch = Chapter.query.filter(
            Chapter.manga_id == manga_id,
            Chapter.team_id == chapter.team_id,
            Chapter.number > chapter.number
        ).order_by(Chapter.number.asc()).first()

        return render_template('chapter_read.html',
                               chapter=chapter,
                               manga=chapter.manga,
                               prev_ch=prev_ch,
                               next_ch=next_ch)

    @app.route('/chapter/<int:chapter_id>/delete', methods=['POST'])
    @login_required
    def chapter_delete(chapter_id):
        chapter = Chapter.query.get_or_404(chapter_id)
        team = chapter.team

        is_admin = current_user.role == 'ADMIN'
        is_uploader = chapter.uploader_id == current_user.id
        is_team_owner = team.owner_id == current_user.id

        if not (is_admin or is_uploader or is_team_owner):
            flash('Нет прав на удаление главы', 'error')
            return redirect(url_for('manga_detail', manga_id=chapter.manga_id))

        manga = chapter.manga
        manga_id = chapter.manga_id

        try:
            for frame in chapter.frames:
                abs_path = os.path.join('static', frame.image_path)
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                    except OSError as e:
                        print(f'Не удалось удалить файл {abs_path}: {e}')

            chapter_dir = os.path.join('static', 'img', 'chapters',
                                       str(chapter.manga_id),
                                       str(chapter.team_id),
                                       str(chapter.id))
            if os.path.isdir(chapter_dir):
                try:
                    for fn in os.listdir(chapter_dir):
                        try:
                            os.remove(os.path.join(chapter_dir, fn))
                        except OSError:
                            pass
                    os.rmdir(chapter_dir)
                except OSError:
                    pass

            db.session.delete(chapter)
            db.session.flush()
            recalc_chapters_count(manga)
            db.session.commit()
            flash('Глава удалена', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при удалении: {e}', 'error')
            print(f'ERROR delete chapter: {e}')

        return redirect(url_for('manga_detail', manga_id=manga_id))

    @app.route('/chapter/<int:chapter_id>/edit', methods=['POST'])
    @login_required
    def chapter_edit(chapter_id):
        chapter = Chapter.query.get_or_404(chapter_id)
        team = chapter.team

        is_admin = current_user.role == 'ADMIN'
        is_uploader = chapter.uploader_id == current_user.id
        is_team_owner = team.owner_id == current_user.id

        if not (is_admin or is_uploader or is_team_owner):
            flash('Нет прав на редактирование', 'error')
            return redirect(url_for('manga_detail', manga_id=chapter.manga_id))

        try:
            title = (request.form.get('title') or '').strip()
            chapter.title = title or None

            vol = request.form.get('volume')
            if vol:
                chapter.volume = int(vol)

            num = request.form.get('number')
            if num:
                new_number = float(num.replace(',', '.'))
                clash = Chapter.query.filter(
                    Chapter.id != chapter.id,
                    Chapter.manga_id == chapter.manga_id,
                    Chapter.team_id == chapter.team_id,
                    Chapter.number == new_number
                ).first()
                if clash:
                    flash(f'Глава с номером {new_number} уже существует у этой команды', 'error')
                    return redirect(url_for('manga_detail', manga_id=chapter.manga_id))
                chapter.number = new_number

            db.session.commit()
            flash('Глава обновлена', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {e}', 'error')

        return redirect(url_for('manga_detail', manga_id=chapter.manga_id))

    @app.route('/admin/add_manga', methods=['GET', 'POST'])
    @admin_required
    def admin_add_manga():
        if request.method == 'POST':
            title = request.form.get('title')
            original_title = request.form.get('original_title')
            release_year = request.form.get('release_year')
            status = request.form.get('status')
            rating = request.form.get('rating', 0.0)
            chapters = request.form.get('chapters', 0)
            volumes = request.form.get('volumes', 0)
            description = request.form.get('description')

            cover_image = request.form.get('cover_image', '')

            if 'cover_file' in request.files:
                file = request.files['cover_file']
                if file and file.filename and allowed_file(file.filename):
                    try:
                        os.makedirs(COVERS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"{uuid.uuid4().hex}.{ext}"
                        filepath = os.path.join(COVERS_FOLDER, unique_name)
                        file.save(filepath)
                        cover_image = f'/static/img/covers/{unique_name}'
                    except Exception as e:
                        flash(f'Ошибка загрузки файла: {str(e)}', 'error')
                        print(f'ERROR: {e}')

            new_manga = Manga(
                title=title,
                original_title=original_title,
                release_year=int(release_year) if release_year else None,
                status=status,
                rating=float(rating) if rating else 0.0,
                chapters_count=int(chapters) if chapters else 0,
                volumes_count=int(volumes) if volumes else 0,
                description=description,
                cover_image=cover_image
            )
            db.session.add(new_manga)
            db.session.commit()

            flash(f'Манга "{title}" успешно добавлена!', 'success')
            return redirect(url_for('catalog'))

        return render_template('admin_add.html')

    @app.route('/admin/hero', methods=['GET'])
    @admin_required
    def admin_hero():
        hero_blocks = HeroBlock.query.order_by(HeroBlock.position).all()
        all_mangas = Manga.query.order_by(Manga.title).all()
        return render_template('admin_hero.html',
                               hero_blocks=hero_blocks,
                               all_mangas=all_mangas)

    @app.route('/admin/hero/<int:block_id>/update', methods=['POST'])
    @admin_required
    def admin_hero_update(block_id):
        block = HeroBlock.query.get_or_404(block_id)

        try:
            manga_id = request.form.get('manga_id')
            if manga_id and manga_id.strip():
                block.manga_id = int(manga_id)
            elif manga_id == '':
                block.manga_id = None

            if 'image_file' in request.files:
                file = request.files['image_file']

                if file and file.filename:
                    if not allowed_file(file.filename):
                        flash(f'Неподдерживаемый формат!', 'error')
                        return redirect(url_for('admin_hero'))

                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_name = f"hero_block_{block.position}_{uuid.uuid4().hex[:8]}.{ext}"
                    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
                    file.save(filepath)

                    if not os.path.exists(filepath):
                        flash('Ошибка сохранения файла!', 'error')
                        return redirect(url_for('admin_hero'))

                    old_file = block.image_filename
                    if old_file and not old_file.startswith('block') and old_file != unique_name:
                        old_path = os.path.join(UPLOAD_FOLDER, old_file)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except OSError as e:
                                print(f'Не удалось удалить старый файл: {e}')

                    block.image_filename = unique_name

            db.session.commit()
            flash(f'Блок #{block.position} успешно обновлён!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
            print(f'ERROR updating hero block: {e}')

        return redirect(url_for('admin_hero'))

    @app.route('/admin/manga/<int:manga_id>/update_cover', methods=['POST'])
    @admin_required
    def admin_update_cover(manga_id):
        manga = Manga.query.get_or_404(manga_id)

        if 'cover_file' not in request.files:
            flash('Файл не был загружен!', 'error')
            return redirect(url_for('admin_mangas'))

        file = request.files['cover_file']

        if not file or not file.filename:
            flash('Файл не выбран!', 'error')
            return redirect(url_for('admin_mangas'))

        if not allowed_file(file.filename):
            flash(f'Неподдерживаемый формат!', 'error')
            return redirect(url_for('admin_mangas'))

        try:
            os.makedirs(COVERS_FOLDER, exist_ok=True)
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"cover_{manga_id}_{uuid.uuid4().hex[:8]}.{ext}"
            filepath = os.path.join(COVERS_FOLDER, unique_name)
            file.save(filepath)

            if not os.path.exists(filepath):
                flash('Ошибка сохранения файла!', 'error')
                return redirect(url_for('admin_mangas'))

            if manga.cover_image and '/static/img/covers/' in manga.cover_image:
                old_filename = manga.cover_image.split('/')[-1].split('?')[0]
                old_path = os.path.join(COVERS_FOLDER, old_filename)
                if os.path.exists(old_path) and old_filename != unique_name:
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            manga.cover_image = f'/static/img/covers/{unique_name}'
            db.session.commit()

            flash(f'Обложка для "{manga.title}" успешно обновлена!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при загрузке: {str(e)}', 'error')
            print(f'ERROR uploading cover: {e}')

        return redirect(url_for('admin_mangas'))

    @app.route('/admin/manga/<int:manga_id>/edit', methods=['POST'])
    @admin_required
    def admin_edit_manga(manga_id):
        manga = Manga.query.get_or_404(manga_id)

        try:
            title = request.form.get('title', '').strip()
            original_title = request.form.get('original_title', '').strip()
            description = request.form.get('description', '').strip()
            status = request.form.get('status', '').strip()
            release_year = request.form.get('release_year', '').strip()
            rating = request.form.get('rating', '').strip()
            chapters = request.form.get('chapters', '').strip()
            volumes = request.form.get('volumes', '').strip()

            if title:
                manga.title = title
            if original_title:
                manga.original_title = original_title
            if description:
                manga.description = description
            if status:
                manga.status = status
            if release_year:
                manga.release_year = int(release_year)
            if rating:
                manga.rating = float(rating)
            if chapters:
                manga.chapters_count = int(chapters)
            if volumes:
                manga.volumes_count = int(volumes)

            if 'cover_file' in request.files:
                file = request.files['cover_file']
                if file and file.filename:
                    if not allowed_file(file.filename):
                        flash(f'Неподдерживаемый формат файла!', 'error')
                        return redirect(request.referrer or url_for('catalog'))

                    os.makedirs(COVERS_FOLDER, exist_ok=True)
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_name = f"cover_{manga_id}_{uuid.uuid4().hex[:8]}.{ext}"
                    filepath = os.path.join(COVERS_FOLDER, unique_name)
                    file.save(filepath)

                    if os.path.exists(filepath):
                        if manga.cover_image and '/static/img/covers/' in manga.cover_image:
                            old_filename = manga.cover_image.split('/')[-1].split('?')[0]
                            old_path = os.path.join(COVERS_FOLDER, old_filename)
                            if os.path.exists(old_path) and old_filename != unique_name:
                                try:
                                    os.remove(old_path)
                                except OSError:
                                    pass
                        manga.cover_image = f'/static/img/covers/{unique_name}'

            cover_url = request.form.get('cover_url', '').strip()
            if cover_url and not (request.files.get('cover_file') and request.files['cover_file'].filename):
                manga.cover_image = cover_url

            db.session.commit()
            flash(f'Манга "{manga.title}" успешно обновлена!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка обновления: {str(e)}', 'error')
            print(f'ERROR editing manga: {e}')

        return redirect(request.referrer or url_for('catalog'))

    @app.route('/admin/manga/<int:manga_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_manga(manga_id):
        manga = Manga.query.get_or_404(manga_id)

        try:
            title = manga.title

            for chapter in list(manga.chapters):
                for frame in chapter.frames:
                    abs_path = os.path.join('static', frame.image_path)
                    if os.path.exists(abs_path):
                        try:
                            os.remove(abs_path)
                        except OSError:
                            pass

            manga_chapters_dir = os.path.join('static', 'img', 'chapters', str(manga.id))
            if os.path.isdir(manga_chapters_dir):
                try:
                    for root, dirs, files in os.walk(manga_chapters_dir, topdown=False):
                        for f in files:
                            try: os.remove(os.path.join(root, f))
                            except OSError: pass
                        for d in dirs:
                            try: os.rmdir(os.path.join(root, d))
                            except OSError: pass
                    os.rmdir(manga_chapters_dir)
                except OSError:
                    pass

            if manga.cover_image and '/static/img/covers/' in manga.cover_image:
                old_filename = manga.cover_image.split('/')[-1].split('?')[0]
                old_path = os.path.join(COVERS_FOLDER, old_filename)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            db.session.delete(manga)
            db.session.commit()
            flash(f'Манга "{title}" удалена!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка удаления: {str(e)}', 'error')

        return redirect(url_for('catalog'))

    @app.route('/admin/mangas')
    @admin_required
    def admin_mangas():
        mangas = Manga.query.order_by(Manga.created_at.desc()).all()
        return render_template('admin_mangas.html', mangas=mangas)

    @app.route('/library')
    @login_required
    def library():
        entries = UserLibrary.query.filter_by(user_id=current_user.id).all()
        return render_template('library.html', entries=entries)

    @app.route('/library/update_progress/<int:entry_id>', methods=['POST'])
    @login_required
    def update_progress(entry_id):
        entry = UserLibrary.query.get_or_404(entry_id)
        if entry.user_id != current_user.id:
            flash('Доступ запрещен', 'error')
            return redirect(url_for('library'))

        chapter = request.form.get('chapter', 0)
        entry.current_chapter = int(chapter) if chapter else 0
        db.session.commit()

        flash('Прогресс чтения успешно обновлен!', 'success')
        return redirect(url_for('library'))

    @app.route('/profile/<username>')
    def profile(username):
        user = User.query.filter_by(username=username).first_or_404()
        library_entries = UserLibrary.query.filter_by(user_id=user.id).all()

        stats = {
            'total': len(library_entries),
            'reading': sum(1 for e in library_entries if e.reading_status == 'READING'),
            'plan_to_read': sum(1 for e in library_entries if e.reading_status == 'PLAN_TO_READ'),
            'completed': sum(1 for e in library_entries if e.reading_status == 'COMPLETED'),
            'on_hold': sum(1 for e in library_entries if e.reading_status == 'ON_HOLD'),
            'dropped': sum(1 for e in library_entries if e.reading_status == 'DROPPED'),
            'chapters': sum(e.current_chapter for e in library_entries if e.current_chapter)
        }

        library_by_status = {
            'READING': [e for e in library_entries if e.reading_status == 'READING'],
            'COMPLETED': [e for e in library_entries if e.reading_status == 'COMPLETED'],
            'PLAN_TO_READ': [e for e in library_entries if e.reading_status == 'PLAN_TO_READ'],
            'ON_HOLD': [e for e in library_entries if e.reading_status == 'ON_HOLD'],
            'DROPPED': [e for e in library_entries if e.reading_status == 'DROPPED'],
        }

        return render_template('profile.html',
                               user=user,
                               stats=stats,
                               library_by_status=library_by_status)

    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        if request.method == 'POST':
            try:
                new_username = request.form.get('username', '').strip()
                if new_username and new_username != current_user.username:
                    if len(new_username) < 3:
                        flash('Ник должен быть не короче 3 символов', 'error')
                        return redirect(url_for('settings'))
                    if len(new_username) > 64:
                        flash('Ник слишком длинный (макс 64 символа)', 'error')
                        return redirect(url_for('settings'))

                    existing = User.query.filter(
                        User.username == new_username,
                        User.id != current_user.id
                    ).first()
                    if existing:
                        flash('Этот ник уже занят', 'error')
                        return redirect(url_for('settings'))

                    current_user.username = new_username

                bio = request.form.get('bio', '').strip()
                current_user.bio = bio if bio else None

                if 'avatar_file' in request.files:
                    file = request.files['avatar_file']
                    if file and file.filename:
                        if not allowed_file(file.filename):
                            flash('Неподдерживаемый формат аватара!', 'error')
                            return redirect(url_for('settings'))

                        os.makedirs(AVATARS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(AVATARS_FOLDER, unique_name)
                        file.save(filepath)

                        if os.path.exists(filepath):
                            if current_user.avatar and '/static/img/avatars/' in current_user.avatar:
                                old_filename = current_user.avatar.split('/')[-1].split('?')[0]
                                old_path = os.path.join(AVATARS_FOLDER, old_filename)
                                if os.path.exists(old_path) and old_filename != unique_name:
                                    try:
                                        os.remove(old_path)
                                    except OSError:
                                        pass
                            current_user.avatar = f'/static/img/avatars/{unique_name}'

                if 'banner_file' in request.files:
                    file = request.files['banner_file']
                    if file and file.filename:
                        if not allowed_file(file.filename):
                            flash('Неподдерживаемый формат баннера!', 'error')
                            return redirect(url_for('settings'))

                        os.makedirs(BANNERS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"banner_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(BANNERS_FOLDER, unique_name)
                        file.save(filepath)

                        if os.path.exists(filepath):
                            if current_user.banner and '/static/img/banners/' in current_user.banner:
                                old_filename = current_user.banner.split('/')[-1].split('?')[0]
                                old_path = os.path.join(BANNERS_FOLDER, old_filename)
                                if os.path.exists(old_path) and old_filename != unique_name:
                                    try:
                                        os.remove(old_path)
                                    except OSError:
                                        pass
                            current_user.banner = f'/static/img/banners/{unique_name}'

                if request.form.get('remove_avatar') == '1':
                    if current_user.avatar and '/static/img/avatars/' in current_user.avatar:
                        old_filename = current_user.avatar.split('/')[-1].split('?')[0]
                        old_path = os.path.join(AVATARS_FOLDER, old_filename)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except OSError:
                                pass
                    current_user.avatar = None

                if request.form.get('remove_banner') == '1':
                    if current_user.banner and '/static/img/banners/' in current_user.banner:
                        old_filename = current_user.banner.split('/')[-1].split('?')[0]
                        old_path = os.path.join(BANNERS_FOLDER, old_filename)
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except OSError:
                                pass
                    current_user.banner = None

                db.session.commit()
                flash('Настройки профиля успешно обновлены!', 'success')
                return redirect(url_for('profile', username=current_user.username))

            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')
                print(f'ERROR updating settings: {e}')
                return redirect(url_for('settings'))

        return render_template('settings.html')

    # ============================================================
    # 🎨 СИСТЕМА УКРАШЕНИЙ (РАМКИ ДЛЯ АВАТАРОК)
    # ============================================================

    @app.route('/settings/frames')
    @login_required
    def frames_shop():
        frames = AvatarFrame.query.filter_by(is_active=True).order_by(
            AvatarFrame.is_premium,
            AvatarFrame.sort_order,
            AvatarFrame.id
        ).all()
        return render_template('frames_shop.html', frames=frames)

    @app.route('/settings/frames/set/<int:frame_id>', methods=['POST'])
    @login_required
    def set_frame(frame_id):
        frame = AvatarFrame.query.get_or_404(frame_id)

        if not current_user.has_frame(frame):
            flash('Эта рамка вам недоступна 🔒', 'error')
            return redirect(url_for('frames_shop'))

        current_user.active_frame_id = frame.id
        db.session.commit()
        flash(f'Рамка «{frame.name}» установлена! ✨', 'success')
        return redirect(url_for('frames_shop'))

    @app.route('/settings/frames/remove', methods=['POST'])
    @login_required
    def remove_frame():
        current_user.active_frame_id = None
        db.session.commit()
        flash('Рамка снята', 'success')
        return redirect(url_for('frames_shop'))

    # ============================================================
    # 🖼️ СИСТЕМА БАННЕРОВ ПРОФИЛЯ
    # ============================================================

    @app.route('/settings/banners')
    @login_required
    def banners_shop():
        banners = ProfileBanner.query.filter_by(is_active=True).order_by(
            ProfileBanner.is_premium,
            ProfileBanner.sort_order,
            ProfileBanner.id
        ).all()
        return render_template('banners_shop.html', banners=banners)

    @app.route('/settings/banners/set/<int:banner_id>', methods=['POST'])
    @login_required
    def set_banner(banner_id):
        banner = ProfileBanner.query.get_or_404(banner_id)

        if not current_user.has_banner(banner):
            flash('Этот баннер вам недоступен 🔒', 'error')
            return redirect(url_for('banners_shop'))

        current_user.active_banner_id = banner.id
        db.session.commit()
        flash(f'Баннер «{banner.name}» установлен! ✨', 'success')
        return redirect(url_for('banners_shop'))

    @app.route('/settings/banners/remove', methods=['POST'])
    @login_required
    def remove_banner():
        current_user.active_banner_id = None
        db.session.commit()
        flash('Баннер профиля убран', 'success')
        return redirect(url_for('banners_shop'))

    @app.route('/premium')
    def premium():
        return render_template('premium.html')

    @app.route('/premium/subscribe', methods=['POST'])
    @login_required
    def subscribe_premium():
        # В реальном приложении здесь будет интеграция с платежкой.
        # Пока просто даём подписку на 30 дней (или добавляем 30 дней)
        user = current_user
        now = datetime.utcnow()
        if user.is_premium and user.premium_until and user.premium_until > now:
            user.premium_until += timedelta(days=30)
        else:
            user.is_premium = True
            user.premium_until = now + timedelta(days=30)
            
        db.session.commit()
        flash('🎉 Вы успешно приобрели Премиум-подписку на 30 дней! Наслаждайтесь чтением платных глав!', 'success')
        return redirect(url_for('premium'))

    @app.route('/admin/frames')
    @admin_required
    def admin_frames():
        frames = AvatarFrame.query.order_by(AvatarFrame.sort_order, AvatarFrame.id).all()
        return render_template('admin_frames.html', frames=frames)

    @app.route('/admin/frames/add', methods=['POST'])
    @admin_required
    def admin_add_frame():
        try:
            code = request.form.get('code', '').strip().lower()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            rarity = request.form.get('rarity', 'common').strip()
            is_premium = request.form.get('is_premium') == 'on'
            sort_order = int(request.form.get('sort_order', 0) or 0)
            glow_class = request.form.get('glow_class', 'glow-blue').strip()

            if not code or not name:
                flash('Заполните код и название!', 'error')
                return redirect(url_for('admin_frames'))

            if AvatarFrame.query.filter_by(code=code).first():
                flash(f'Рамка с кодом "{code}" уже существует', 'error')
                return redirect(url_for('admin_frames'))

            if 'frame_file' not in request.files or not request.files['frame_file'].filename:
                flash('Загрузите PNG-файл рамки', 'error')
                return redirect(url_for('admin_frames'))

            file = request.files['frame_file']
            if not allowed_file(file.filename):
                flash('Неподдерживаемый формат файла!', 'error')
                return redirect(url_for('admin_frames'))

            os.makedirs(FRAMES_FOLDER, exist_ok=True)
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{code}_{uuid.uuid4().hex[:6]}.{ext}"
            filepath = os.path.join(FRAMES_FOLDER, unique_name)
            file.save(filepath)

            frame = AvatarFrame(
                code=code,
                name=name,
                description=description or None,
                image=f'img/frames/{unique_name}',
                rarity=rarity,
                is_premium=is_premium,
                sort_order=sort_order,
                glow_class=glow_class
            )
            db.session.add(frame)
            db.session.commit()
            flash(f'Рамка «{name}» добавлена!', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
            print(f'ERROR add_frame: {e}')

        return redirect(url_for('admin_frames'))

    @app.route('/admin/frames/<int:frame_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_frame(frame_id):
        frame = AvatarFrame.query.get_or_404(frame_id)
        try:
            User.query.filter_by(active_frame_id=frame.id).update({'active_frame_id': None})

            abs_path = os.path.join('static', frame.image)
            if os.path.exists(abs_path):
                try:
                    os.remove(abs_path)
                except OSError:
                    pass

            db.session.delete(frame)
            db.session.commit()
            flash('Рамка удалена', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

        return redirect(url_for('admin_frames'))

    @app.route('/admin/frames/<int:frame_id>/grant', methods=['POST'])
    @admin_required
    def admin_grant_frame(frame_id):
        frame = AvatarFrame.query.get_or_404(frame_id)
        username = request.form.get('username', '').strip()
        user = User.query.filter_by(username=username).first()

        if not user:
            flash(f'Пользователь "{username}" не найден', 'error')
            return redirect(url_for('admin_frames'))

        if user.unlock_frame(frame):
            db.session.commit()
            create_notification(
                user.id,
                'FRAME_UNLOCKED',
                f'🎁 Вам выдана новая рамка: «{frame.name}»! Откройте раздел "Украшения".'
            )
            flash(f'Рамка «{frame.name}» выдана {user.username}', 'success')
        else:
            flash(f'У {user.username} уже есть эта рамка', 'error')

        return redirect(url_for('admin_frames'))

    @app.route('/teams')
    def teams_list():
        teams = TranslationTeam.query.order_by(TranslationTeam.created_at.desc()).all()
        return render_template('teams_list.html', teams=teams)

    @app.route('/teams/apply', methods=['GET', 'POST'])
    @login_required
    def team_apply():
        existing = TeamApplication.query.filter_by(
            user_id=current_user.id,
            status='PENDING'
        ).first()

        if existing:
            flash('У вас уже есть заявка на рассмотрении', 'error')
            return redirect(url_for('my_team_applications'))

        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip()
                short_description = request.form.get('short_description', '').strip()
                full_description = request.form.get('full_description', '').strip()
                languages = request.form.get('languages', '').strip()
                required_roles = request.form.get('required_roles', '').strip()
                reason = request.form.get('reason', '').strip()
                additional_info = request.form.get('additional_info', '').strip()

                if not all([name, short_description, full_description, languages, required_roles, reason]):
                    flash('Заполните все обязательные поля!', 'error')
                    return redirect(url_for('team_apply'))

                if TranslationTeam.query.filter_by(name=name).first():
                    flash('Команда с таким названием уже существует!', 'error')
                    return redirect(url_for('team_apply'))

                logo_path = None
                if 'logo' in request.files:
                    file = request.files['logo']
                    if file and file.filename and allowed_file(file.filename):
                        os.makedirs(TEAMS_LOGOS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"team_logo_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(TEAMS_LOGOS_FOLDER, unique_name)
                        file.save(filepath)
                        logo_path = f'/static/img/teams/logos/{unique_name}'

                application = TeamApplication(
                    user_id=current_user.id,
                    name=name,
                    short_description=short_description,
                    full_description=full_description,
                    languages=languages,
                    required_roles=required_roles,
                    logo=logo_path,
                    reason=reason,
                    additional_info=additional_info
                )
                db.session.add(application)
                db.session.commit()

                admins = User.query.filter_by(role='ADMIN').all()
                for admin in admins:
                    create_notification(
                        admin.id,
                        'TEAM_APPLICATION',
                        f'Новая заявка на создание команды "{name}" от {current_user.username}'
                    )

                flash('Заявка успешно отправлена! Ожидайте рассмотрения.', 'success')
                return redirect(url_for('my_team_applications'))

            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')
                print(f'ERROR: {e}')

        return render_template('team_apply.html')

    @app.route('/teams/my-applications')
    @login_required
    def my_team_applications():
        applications = TeamApplication.query.filter_by(
            user_id=current_user.id
        ).order_by(TeamApplication.created_at.desc()).all()
        return render_template('my_team_applications.html', applications=applications)

    @app.route('/admin/team-applications')
    @admin_required
    def admin_team_applications():
        status_filter = request.args.get('status', 'PENDING')

        query = TeamApplication.query
        if status_filter and status_filter != 'ALL':
            query = query.filter_by(status=status_filter)

        applications = query.order_by(TeamApplication.created_at.desc()).all()

        counts = {
            'pending': TeamApplication.query.filter_by(status='PENDING').count(),
            'approved': TeamApplication.query.filter_by(status='APPROVED').count(),
            'rejected': TeamApplication.query.filter_by(status='REJECTED').count(),
        }

        return render_template('admin_team_applications.html',
                               applications=applications,
                               counts=counts,
                               current_filter=status_filter)

    @app.route('/admin/team-applications/<int:app_id>')
    @admin_required
    def admin_team_application_detail(app_id):
        application = TeamApplication.query.get_or_404(app_id)
        return render_template('admin_team_application_detail.html', application=application)

    @app.route('/admin/team-applications/<int:app_id>/approve', methods=['POST'])
    @admin_required
    def admin_approve_team(app_id):
        application = TeamApplication.query.get_or_404(app_id)

        if application.status != 'PENDING':
            flash('Эта заявка уже обработана!', 'error')
            return redirect(url_for('admin_team_applications'))

        try:
            slug = slugify(application.name)
            base_slug = slug
            counter = 1
            while TranslationTeam.query.filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            team = TranslationTeam(
                owner_id=application.user_id,
                name=application.name,
                slug=slug,
                short_description=application.short_description,
                full_description=application.full_description,
                languages=application.languages,
                logo=application.logo,
                required_roles=application.required_roles,
                is_recruiting=True
            )
            db.session.add(team)
            db.session.flush()

            owner_member = TeamMember(
                team_id=team.id,
                user_id=application.user_id,
                role='OWNER',
                role_label='Владелец'
            )
            db.session.add(owner_member)

            application.status = 'APPROVED'
            application.reviewed_at = datetime.utcnow()
            application.reviewed_by_id = current_user.id

            db.session.commit()

            create_notification(
                application.user_id,
                'TEAM_APPROVED',
                f'🎉 Ваша заявка на создание команды "{application.name}" одобрена!'
            )

            flash(f'Команда "{team.name}" успешно создана!', 'success')
            return redirect(url_for('team_detail', slug=team.slug))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')
            print(f'ERROR: {e}')
            return redirect(url_for('admin_team_applications'))

    @app.route('/admin/team-applications/<int:app_id>/reject', methods=['POST'])
    @admin_required
    def admin_reject_team(app_id):
        application = TeamApplication.query.get_or_404(app_id)

        if application.status != 'PENDING':
            flash('Эта заявка уже обработана!', 'error')
            return redirect(url_for('admin_team_applications'))

        rejection_reason = request.form.get('rejection_reason', '').strip()
        if not rejection_reason:
            flash('Укажите причину отклонения!', 'error')
            return redirect(url_for('admin_team_application_detail', app_id=app_id))

        application.status = 'REJECTED'
        application.rejection_reason = rejection_reason
        application.reviewed_at = datetime.utcnow()
        application.reviewed_by_id = current_user.id
        db.session.commit()

        create_notification(
            application.user_id,
            'TEAM_REJECTED',
            f'❌ Ваша заявка на создание команды "{application.name}" отклонена. Причина: {rejection_reason}'
        )

        flash('Заявка отклонена', 'success')
        return redirect(url_for('admin_team_applications'))

    @app.route('/teams/<slug>')
    def team_detail(slug):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()
        members = team.members.all()
        is_owner = current_user.is_authenticated and current_user.id == team.owner_id
        is_member = False
        if current_user.is_authenticated:
            is_member = TeamMember.query.filter_by(
                team_id=team.id, user_id=current_user.id
            ).first() is not None

        return render_template('team_detail.html',
                               team=team,
                               members=members,
                               is_owner=is_owner,
                               is_member=is_member)

    @app.route('/teams/<slug>/edit', methods=['GET', 'POST'])
    @login_required
    def team_edit(slug):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()

        if team.owner_id != current_user.id:
            flash('Только владелец может редактировать команду!', 'error')
            return redirect(url_for('team_detail', slug=slug))

        if request.method == 'POST':
            try:
                team.short_description = request.form.get('short_description', '').strip()
                team.full_description = request.form.get('full_description', '').strip()
                team.languages = request.form.get('languages', '').strip()
                team.required_roles = request.form.get('required_roles', '').strip()
                team.recruitment_text = request.form.get('recruitment_text', '').strip()
                team.is_recruiting = request.form.get('is_recruiting') == 'on'

                if 'logo' in request.files:
                    file = request.files['logo']
                    if file and file.filename and allowed_file(file.filename):
                        os.makedirs(TEAMS_LOGOS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"team_logo_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(TEAMS_LOGOS_FOLDER, unique_name)
                        file.save(filepath)
                        team.logo = f'/static/img/teams/logos/{unique_name}'

                if 'banner' in request.files:
                    file = request.files['banner']
                    if file and file.filename and allowed_file(file.filename):
                        os.makedirs(TEAMS_BANNERS_FOLDER, exist_ok=True)
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"team_banner_{uuid.uuid4().hex[:8]}.{ext}"
                        filepath = os.path.join(TEAMS_BANNERS_FOLDER, unique_name)
                        file.save(filepath)
                        team.banner = f'/static/img/teams/banners/{unique_name}'

                db.session.commit()
                flash('Команда обновлена!', 'success')
                return redirect(url_for('team_detail', slug=team.slug))

            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')

        return render_template('team_edit.html', team=team)

    @app.route('/teams/<slug>/invite', methods=['POST'])
    @login_required
    def team_invite(slug):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()

        if team.owner_id != current_user.id:
            flash('Только владелец может приглашать!', 'error')
            return redirect(url_for('team_detail', slug=slug))

        username = request.form.get('username', '').strip()
        role = request.form.get('role', 'MEMBER')
        message = request.form.get('message', '').strip()

        user = User.query.filter_by(username=username).first()
        if not user:
            flash(f'Пользователь "{username}" не найден', 'error')
            return redirect(url_for('team_detail', slug=slug))

        if TeamMember.query.filter_by(team_id=team.id, user_id=user.id).first():
            flash(f'{username} уже в команде', 'error')
            return redirect(url_for('team_detail', slug=slug))

        existing = TeamInvitation.query.filter_by(
            team_id=team.id, user_id=user.id, status='PENDING'
        ).first()
        if existing:
            flash(f'{username} уже приглашён', 'error')
            return redirect(url_for('team_detail', slug=slug))

        invitation = TeamInvitation(
            team_id=team.id,
            user_id=user.id,
            invited_by_id=current_user.id,
            role=role,
            message=message
        )
        db.session.add(invitation)
        db.session.commit()

        create_notification(
            user.id,
            'TEAM_INVITATION',
            f'🎉 Вас пригласили в команду "{team.name}" на роль {role}'
        )

        flash(f'Приглашение отправлено {username}!', 'success')
        return redirect(url_for('team_detail', slug=slug))

    @app.route('/invitations/<int:inv_id>/respond', methods=['POST'])
    @login_required
    def respond_invitation(inv_id):
        invitation = TeamInvitation.query.get_or_404(inv_id)

        if invitation.user_id != current_user.id:
            flash('Это не ваше приглашение', 'error')
            return redirect(url_for('my_invitations'))

        action = request.form.get('action')

        if action == 'accept':
            member = TeamMember(
                team_id=invitation.team_id,
                user_id=current_user.id,
                role=invitation.role
            )
            db.session.add(member)
            invitation.status = 'ACCEPTED'
            flash(f'Вы вступили в команду "{invitation.team.name}"!', 'success')
        elif action == 'decline':
            invitation.status = 'DECLINED'
            flash('Приглашение отклонено', 'success')

        db.session.commit()
        return redirect(url_for('my_invitations'))

    @app.route('/invitations')
    @login_required
    def my_invitations():
        invitations = TeamInvitation.query.filter_by(
            user_id=current_user.id, status='PENDING'
        ).order_by(TeamInvitation.created_at.desc()).all()
        return render_template('my_invitations.html', invitations=invitations)

    @app.route('/teams/<slug>/members/<int:member_id>/remove', methods=['POST'])
    @login_required
    def team_remove_member(slug, member_id):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()

        if team.owner_id != current_user.id:
            flash('Только владелец может удалять участников', 'error')
            return redirect(url_for('team_detail', slug=slug))

        member = TeamMember.query.get_or_404(member_id)
        if member.role == 'OWNER':
            flash('Нельзя удалить владельца', 'error')
            return redirect(url_for('team_detail', slug=slug))

        db.session.delete(member)
        db.session.commit()
        flash('Участник удалён', 'success')
        return redirect(url_for('team_detail', slug=slug))

    @app.route('/teams/<slug>/projects/add', methods=['GET', 'POST'])
    @login_required
    def team_add_project(slug):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()

        is_owner = team.owner_id == current_user.id
        is_member = TeamMember.query.filter_by(
            team_id=team.id, user_id=current_user.id
        ).first() is not None

        if not (is_owner or is_member):
            flash('Только участники команды могут добавлять проекты', 'error')
            return redirect(url_for('team_detail', slug=slug))

        if request.method == 'POST':
            manga_id = request.form.get('manga_id')
            if not manga_id:
                flash('Выберите мангу!', 'error')
                return redirect(url_for('team_add_project', slug=slug))

            try:
                manga = Manga.query.get_or_404(int(manga_id))

                if manga in team.projects:
                    flash(f'"{manga.title}" уже в проектах команды', 'error')
                    return redirect(url_for('team_detail', slug=slug))

                team.projects.append(manga)
                db.session.commit()

                flash(f'"{manga.title}" добавлена в проекты команды!', 'success')
                return redirect(url_for('team_detail', slug=slug))

            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')
                print(f'ERROR: {e}')

        search_query = request.args.get('search', '').strip()

        mangas_query = Manga.query
        if search_query:
            mangas_query = mangas_query.filter(
                Manga.title.ilike(f"%{search_query}%") |
                Manga.original_title.ilike(f"%{search_query}%")
            )

        team_project_ids = [m.id for m in team.projects]
        if team_project_ids:
            mangas_query = mangas_query.filter(~Manga.id.in_(team_project_ids))

        all_mangas = mangas_query.order_by(Manga.title).limit(50).all()

        return render_template('team_add_project.html',
                               team=team,
                               mangas=all_mangas,
                               search_query=search_query)

    @app.route('/teams/<slug>/projects/<int:manga_id>/remove', methods=['POST'])
    @login_required
    def team_remove_project(slug, manga_id):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()

        if team.owner_id != current_user.id:
            flash('Только владелец может удалять проекты', 'error')
            return redirect(url_for('team_detail', slug=slug))

        try:
            manga = Manga.query.get_or_404(manga_id)

            if manga in team.projects:
                team.projects.remove(manga)
                db.session.commit()
                flash(f'"{manga.title}" удалена из проектов команды', 'success')
            else:
                flash('Эта манга не в проектах команды', 'error')

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

        return redirect(url_for('team_detail', slug=slug))

    @app.route('/forum')
    def forum():
        page = request.args.get('page', 1, type=int)
        search = request.args.get('q', '').strip()

        query = ForumTopic.query
        if search:
            query = query.filter(ForumTopic.title.ilike(f'%{search}%'))

        topics = query.order_by(
            ForumTopic.is_pinned.desc(),
            ForumTopic.created_at.desc()
        ).paginate(page=page, per_page=20, error_out=False)

        return render_template('forum.html', topics=topics, search=search)

    @app.route('/forum/create', methods=['GET', 'POST'])
    @login_required
    def forum_create():
        if current_user.is_banned:
            flash('Забаненные пользователи не могут создавать темы', 'error')
            return redirect(url_for('forum'))

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            content = request.form.get('content', '').strip()

            if not title or len(title) < 3:
                flash('Название темы должно быть не короче 3 символов', 'error')
                return redirect(url_for('forum_create'))

            if not content or len(content) < 5:
                flash('Сообщение должно быть не короче 5 символов', 'error')
                return redirect(url_for('forum_create'))

            try:
                topic = ForumTopic(
                    title=title,
                    description=description if description else None,
                    author_id=current_user.id
                )
                db.session.add(topic)
                db.session.flush()

                first_post = ForumPost(
                    topic_id=topic.id,
                    author_id=current_user.id,
                    content=content
                )
                db.session.add(first_post)
                db.session.commit()

                flash('Тема создана!', 'success')
                return redirect(url_for('forum_topic', topic_id=topic.id))

            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')
                print(f'ERROR forum_create: {e}')

        return render_template('forum_create.html')

    @app.route('/forum/topic/<int:topic_id>', methods=['GET', 'POST'])
    def forum_topic(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)

        topic.views = (topic.views or 0) + 1
        db.session.commit()

        if request.method == 'POST':
            if not current_user.is_authenticated:
                flash('Войдите, чтобы писать в темах', 'error')
                return redirect(url_for('login'))

            if current_user.is_banned:
                flash('Забаненные пользователи не могут писать сообщения', 'error')
                return redirect(url_for('forum_topic', topic_id=topic.id))

            if topic.is_closed:
                flash('Тема закрыта для обсуждения', 'error')
                return redirect(url_for('forum_topic', topic_id=topic.id))

            content = request.form.get('content', '').strip()
            if not content or len(content) < 2:
                flash('Сообщение слишком короткое', 'error')
                return redirect(url_for('forum_topic', topic_id=topic.id))

            try:
                post = ForumPost(
                    topic_id=topic.id,
                    author_id=current_user.id,
                    content=content
                )
                db.session.add(post)
                db.session.commit()
                flash('Сообщение добавлено!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'error')
                print(f'ERROR forum reply: {e}')

            return redirect(url_for('forum_topic', topic_id=topic.id))

        page = request.args.get('page', 1, type=int)
        posts = topic.posts.order_by(ForumPost.created_at.asc()).paginate(
            page=page, per_page=20, error_out=False
        )

        return render_template('forum_topic.html', topic=topic, posts=posts)

    @app.route('/forum/topic/<int:topic_id>/delete', methods=['POST'])
    @login_required
    def forum_topic_delete(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)
        if topic.author_id != current_user.id and current_user.role not in ('ADMIN', 'MODERATOR'):
            flash('Нет прав на удаление', 'error')
            return redirect(url_for('forum_topic', topic_id=topic.id))

        try:
            db.session.delete(topic)
            db.session.commit()
            flash('Тема удалена', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

        return redirect(url_for('forum'))

    @app.route('/forum/post/<int:post_id>/delete', methods=['POST'])
    @login_required
    def forum_post_delete(post_id):
        post = ForumPost.query.get_or_404(post_id)
        if post.author_id != current_user.id and current_user.role not in ('ADMIN', 'MODERATOR'):
            flash('Нет прав на удаление', 'error')
            return redirect(url_for('forum_topic', topic_id=post.topic_id))

        topic_id = post.topic_id

        try:
            first_post = ForumPost.query.filter_by(topic_id=topic_id).order_by(
                ForumPost.created_at.asc()
            ).first()
            if first_post and first_post.id == post.id:
                topic = ForumTopic.query.get(topic_id)
                db.session.delete(topic)
                db.session.commit()
                flash('Тема удалена (первое сообщение нельзя удалить отдельно)', 'success')
                return redirect(url_for('forum'))

            db.session.delete(post)
            db.session.commit()
            flash('Сообщение удалено', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {str(e)}', 'error')

        return redirect(url_for('forum_topic', topic_id=topic_id))

    @app.route('/forum/topic/<int:topic_id>/toggle-pin', methods=['POST'])
    @moderator_required
    def forum_topic_toggle_pin(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)
        topic.is_pinned = not topic.is_pinned
        db.session.commit()
        log_moderation_action(
            'PIN_TOPIC' if topic.is_pinned else 'UNPIN_TOPIC',
            'FORUM_TOPIC', topic.id
        )
        flash('Закреплено' if topic.is_pinned else 'Откреплено', 'success')
        return redirect(url_for('forum_topic', topic_id=topic.id))

    @app.route('/forum/topic/<int:topic_id>/toggle-close', methods=['POST'])
    @moderator_required
    def forum_topic_toggle_close(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)
        topic.is_closed = not topic.is_closed
        db.session.commit()
        log_moderation_action(
            'CLOSE_TOPIC' if topic.is_closed else 'OPEN_TOPIC',
            'FORUM_TOPIC', topic.id
        )
        flash('Тема закрыта' if topic.is_closed else 'Тема открыта', 'success')
        return redirect(url_for('forum_topic', topic_id=topic.id))

    @app.route('/admin/moderators')
    @admin_required
    def admin_moderators():
        moderators = User.query.filter_by(role='MODERATOR').all()
        all_users = User.query.filter(User.role == 'USER').order_by(User.username).all()
        return render_template('admin_moderators.html',
                               moderators=moderators,
                               all_users=all_users)

    @app.route('/admin/moderators/assign', methods=['POST'])
    @admin_required
    def admin_assign_moderator():
        user_id = request.form.get('user_id')
        if not user_id:
            flash('Выберите пользователя!', 'error')
            return redirect(url_for('admin_moderators'))

        user = User.query.get_or_404(int(user_id))
        if user.role == 'ADMIN':
            flash('Нельзя назначить админа модератором', 'error')
            return redirect(url_for('admin_moderators'))

        user.role = 'MODERATOR'
        db.session.commit()

        create_notification(
            user.id,
            'MODERATOR_ASSIGNED',
            f'🛡️ Поздравляем! Вы назначены модератором сайта!'
        )

        log_moderation_action('ASSIGN_MODERATOR', 'USER', user.id,
                              f'Назначен модератором админом {current_user.username}')

        flash(f'{user.username} назначен модератором!', 'success')
        return redirect(url_for('admin_moderators'))

    @app.route('/admin/moderators/<int:user_id>/revoke', methods=['POST'])
    @admin_required
    def admin_revoke_moderator(user_id):
        user = User.query.get_or_404(user_id)
        if user.role != 'MODERATOR':
            flash('Этот пользователь не модератор', 'error')
            return redirect(url_for('admin_moderators'))

        user.role = 'USER'
        db.session.commit()

        create_notification(
            user.id,
            'MODERATOR_REVOKED',
            f'Ваши права модератора были отозваны'
        )

        log_moderation_action('REVOKE_MODERATOR', 'USER', user.id)

        flash(f'Права модератора у {user.username} отозваны', 'success')
        return redirect(url_for('admin_moderators'))

    @app.route('/moderation')
    @moderator_required
    def moderation_panel():
        stats = {
            'total_users': User.query.count(),
            'total_comments': Comment.query.count(),
            'total_topics': ForumTopic.query.count(),
            'total_posts': ForumPost.query.count(),
            'banned_users': UserBan.query.filter_by(is_active=True).count(),
        }

        recent_actions = ModerationLog.query.order_by(
            ModerationLog.created_at.desc()
        ).limit(20).all()

        recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(15).all()
        recent_posts = ForumPost.query.order_by(ForumPost.created_at.desc()).limit(15).all()
        active_bans = UserBan.query.filter_by(is_active=True).order_by(
            UserBan.created_at.desc()
        ).limit(20).all()

        return render_template('moderation_panel.html',
                               stats=stats,
                               recent_actions=recent_actions,
                               recent_comments=recent_comments,
                               recent_posts=recent_posts,
                               active_bans=active_bans)

    @app.route('/moderation/ban_user/<int:user_id>', methods=['POST'])
    @moderator_required
    def mod_ban_user(user_id):
        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            flash('Нельзя забанить самого себя!', 'error')
            return redirect(request.referrer or url_for('moderation_panel'))

        if user.role == 'ADMIN':
            flash('Нельзя забанить администратора!', 'error')
            return redirect(request.referrer or url_for('moderation_panel'))

        if user.role == 'MODERATOR' and current_user.role != 'ADMIN':
            flash('Только админ может банить модераторов', 'error')
            return redirect(request.referrer or url_for('moderation_panel'))

        reason = request.form.get('reason', '').strip()
        if not reason:
            flash('Укажите причину бана', 'error')
            return redirect(request.referrer or url_for('moderation_panel'))

        days = request.form.get('days', '').strip()
        banned_until = None
        if days and days.isdigit() and int(days) > 0:
            banned_until = datetime.utcnow() + timedelta(days=int(days))

        existing = UserBan.query.filter_by(user_id=user.id, is_active=True).first()
        if existing:
            existing.is_active = False

        ban = UserBan(
            user_id=user.id,
            banned_by_id=current_user.id,
            reason=reason,
            banned_until=banned_until
        )
        db.session.add(ban)
        db.session.commit()

        duration = f'до {banned_until.strftime("%d.%m.%Y")}' if banned_until else 'навсегда'
        create_notification(
            user.id,
            'USER_BANNED',
            f'🚫 Вы были забанены {duration}. Причина: {reason}'
        )

        log_moderation_action('BAN_USER', 'USER', user.id, reason)

        flash(f'Пользователь {user.username} забанен {duration}', 'success')
        return redirect(request.referrer or url_for('moderation_panel'))

    @app.route('/moderation/unban_user/<int:user_id>', methods=['POST'])
    @moderator_required
    def mod_unban_user(user_id):
        user = User.query.get_or_404(user_id)

        ban = UserBan.query.filter_by(user_id=user.id, is_active=True).first()
        if not ban:
            flash('Пользователь не забанен', 'error')
            return redirect(request.referrer or url_for('moderation_panel'))

        ban.is_active = False
        db.session.commit()

        create_notification(
            user.id,
            'USER_UNBANNED',
            f'✅ Ваш бан был снят. Добро пожаловать обратно!'
        )

        log_moderation_action('UNBAN_USER', 'USER', user.id)

        flash(f'Бан с {user.username} снят', 'success')
        return redirect(request.referrer or url_for('moderation_panel'))

    @app.route('/moderation/comment/<int:comment_id>/delete', methods=['POST'])
    @moderator_required
    def mod_delete_comment(comment_id):
        comment = Comment.query.get_or_404(comment_id)
        reason = request.form.get('reason', 'Нарушение правил').strip()

        manga_id = comment.manga_id
        author_id = comment.user_id
        author_name = comment.user.username if comment.user else 'неизвестный'

        try:
            db.session.delete(comment)
            db.session.commit()

            create_notification(
                author_id,
                'COMMENT_DELETED',
                f'⚠️ Ваш комментарий удалён модератором. Причина: {reason}'
            )

            log_moderation_action('DELETE_COMMENT', 'COMMENT', comment_id,
                                  f'Автор: {author_name}. Причина: {reason}')

            flash('Комментарий удалён', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {e}', 'error')

        return redirect(request.referrer or url_for('manga_detail', manga_id=manga_id))

    @app.route('/moderation/forum/post/<int:post_id>/delete', methods=['POST'])
    @moderator_required
    def mod_delete_forum_post(post_id):
        post = ForumPost.query.get_or_404(post_id)
        reason = request.form.get('reason', 'Нарушение правил').strip()

        topic_id = post.topic_id
        author_id = post.author_id
        author_name = post.author.username if post.author else 'неизвестный'

        try:
            first_post = ForumPost.query.filter_by(topic_id=topic_id).order_by(
                ForumPost.created_at.asc()
            ).first()

            if first_post and first_post.id == post.id:
                topic = ForumTopic.query.get(topic_id)
                db.session.delete(topic)
                log_moderation_action('DELETE_FORUM_TOPIC', 'FORUM_TOPIC', topic_id, reason)
                msg_redirect = url_for('forum')
            else:
                db.session.delete(post)
                log_moderation_action('DELETE_FORUM_POST', 'FORUM_POST', post_id,
                                      f'Автор: {author_name}. Причина: {reason}')
                msg_redirect = url_for('forum_topic', topic_id=topic_id)

            db.session.commit()

            create_notification(
                author_id,
                'FORUM_POST_DELETED',
                f'⚠️ Ваше сообщение на форуме удалено модератором. Причина: {reason}'
            )

            flash('Сообщение удалено', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка: {e}', 'error')
            msg_redirect = url_for('forum')

        return redirect(msg_redirect)

    @app.route('/moderation/users')
    @moderator_required
    def mod_users_list():
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)

        query = User.query
        if search:
            query = query.filter(User.username.ilike(f'%{search}%'))

        users = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=30, error_out=False
        )

        banned_user_ids = set(b.user_id for b in UserBan.query.filter_by(is_active=True).all())

        return render_template('mod_users_list.html',
                               users=users,
                               search=search,
                               banned_user_ids=banned_user_ids)

    @app.route('/moderation/logs')
    @moderator_required
    def mod_logs():
        page = request.args.get('page', 1, type=int)
        logs = ModerationLog.query.order_by(ModerationLog.created_at.desc()).paginate(
            page=page, per_page=50, error_out=False
        )
        return render_template('mod_logs.html', logs=logs)

    # ============================================================
    # 💬 ЧАТ С БОТОМ-МОДЕРАТОРОМ
    # ============================================================

    @app.route('/chat')
    @login_required
    def chat():
        general = ChatRoom.query.filter_by(room_type='general').first()
        mod_room = None
        if current_user.role in ('MODERATOR', 'ADMIN'):
            mod_room = ChatRoom.query.filter_by(room_type='moderators').first()
        return render_template('chat.html', general=general, mod_room=mod_room)

    @app.route('/chat/api/messages/<int:room_id>')
    @login_required
    def chat_api_messages(room_id):
        room = ChatRoom.query.get_or_404(room_id)

        if room.room_type == 'moderators' and current_user.role not in ('MODERATOR', 'ADMIN'):
            return jsonify({'error': 'Нет доступа'}), 403

        messages = ChatMessage.query.filter_by(room_id=room_id, is_deleted=False) \
            .order_by(ChatMessage.created_at.desc()).limit(80).all()
        messages.reverse()

        return jsonify([{
            'id': m.id,
            'user_id': m.user_id,
            'username': m.user.username if m.user else 'Удалён',
            'avatar': url_for('static', filename=m.user.avatar) if m.user and m.user.avatar else f"https://ui-avatars.com/api/?name={m.user.username if m.user else 'User'}&background=1A1F2E&color=06b6d4&bold=true",
            'role': m.user.role if m.user else 'USER',
            'content': m.content,
            'time': m.created_at.strftime('%H:%M'),
            'is_bot': m.is_bot,
            'is_me': m.user_id == current_user.id
        } for m in messages])

    @app.route('/chat/api/send/<int:room_id>', methods=['POST'])
    @login_required
    def chat_api_send(room_id):
        room = ChatRoom.query.get_or_404(room_id)

        if room.room_type == 'moderators' and current_user.role not in ('MODERATOR', 'ADMIN'):
            return jsonify({'error': 'Нет доступа'}), 403

        if current_user.is_banned:
            return jsonify({'error': 'Вы забанены'}), 403

        data = request.get_json() or {}
        text_content = (data.get('content') or '').strip()

        if not text_content:
            return jsonify({'error': 'Пустое сообщение'}), 400
        if len(text_content) > 500:
            return jsonify({'error': 'Слишком длинное сообщение (макс 500)'}), 400

        # Проверка ботом
        result = ChatBot.process_message(current_user, room_id, text_content)
        if not result['allowed']:
            return jsonify({'error': result['message'], 'muted': result['muted']}), 403

        msg = ChatMessage(
            room_id=room_id,
            user_id=current_user.id,
            content=text_content
        )
        db.session.add(msg)
        db.session.commit()

        return jsonify({'success': True, 'id': msg.id})

    @app.route('/chat/api/delete/<int:msg_id>', methods=['POST'])
    @login_required
    def chat_api_delete(msg_id):
        msg = ChatMessage.query.get_or_404(msg_id)

        if current_user.role not in ('MODERATOR', 'ADMIN') and msg.user_id != current_user.id:
            return jsonify({'error': 'Нет прав'}), 403

        msg.is_deleted = True
        db.session.commit()

        if current_user.role in ('MODERATOR', 'ADMIN') and msg.user_id != current_user.id:
            log_moderation_action('DELETE_CHAT_MESSAGE', 'CHAT_MESSAGE', msg.id,
                                  f'Автор: {msg.user.username if msg.user else "?"}')

        return jsonify({'success': True})

    @app.route('/chat/api/mute/<int:user_id>', methods=['POST'])
    @moderator_required
    def chat_api_mute(user_id):
        user = User.query.get_or_404(user_id)

        if user.role == 'ADMIN':
            return jsonify({'error': 'Нельзя замутить админа'}), 403

        data = request.get_json() or {}
        minutes = int(data.get('minutes', 30))
        reason = (data.get('reason') or 'Нарушение правил чата').strip()

        ChatBot.mute_user(user.id, minutes=minutes, reason=reason)

        general = ChatRoom.query.filter_by(room_type='general').first()
        if general:
            ChatBot.send_bot_message(
                general.id,
                f"🔇 Модератор @{current_user.username} замутил @{user.username} на {minutes} мин. Причина: {reason}"
            )

        log_moderation_action('MUTE_CHAT', 'USER', user.id, f'{minutes} мин. {reason}')

        return jsonify({'success': True})

    @app.route('/support')
    def support():
        return render_template('support.html')

    @app.route('/notifications')
    @login_required
    def notifications():
        notifs = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(Notification.created_at.desc()).limit(50).all()

        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()

        return render_template('notifications.html', notifications=notifs)

    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.utcnow}

    @app.context_processor
    def inject_global_counts():
        counts = {
            'unread_notifications_count': 0,
            'pending_invitations_count': 0,
            'pending_team_apps_count': 0,
            'is_moderator': False,
            'is_admin': False,
            'chat_muted': False,
        }

        if current_user.is_authenticated:
            try:
                counts['unread_notifications_count'] = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()

                counts['pending_invitations_count'] = TeamInvitation.query.filter_by(
                    user_id=current_user.id, status='PENDING'
                ).count()

                counts['is_moderator'] = current_user.role in ('MODERATOR', 'ADMIN')
                counts['is_admin'] = current_user.role == 'ADMIN'

                try:
                    mute = ChatBot.get_active_mute(current_user.id)
                    counts['chat_muted'] = mute is not None
                except Exception:
                    counts['chat_muted'] = False

                if current_user.role == 'ADMIN':
                    counts['pending_team_apps_count'] = TeamApplication.query.filter_by(
                        status='PENDING'
                    ).count()
            except Exception as e:
                print(f'Context processor error: {e}')

        return counts

    auto_update_database(app)

    return app


app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)