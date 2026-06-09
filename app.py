import os
import re
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, inspect
from models import (db, User, Genre, Manga, Comment, UserLibrary, HeroBlock,
                    Notification, TeamApplication, TranslationTeam,
                    TeamMember, TeamInvitation, ForumTopic, ForumPost,
                    Chapter, ChapterFrame)


# ============ КОНФИГ ============
UPLOAD_FOLDER = os.path.join('static', 'img')
COVERS_FOLDER = os.path.join('static', 'img', 'covers')
AVATARS_FOLDER = os.path.join('static', 'img', 'avatars')
BANNERS_FOLDER = os.path.join('static', 'img', 'banners')
TEAMS_LOGOS_FOLDER = os.path.join('static', 'img', 'teams', 'logos')
TEAMS_BANNERS_FOLDER = os.path.join('static', 'img', 'teams', 'banners')
CHAPTERS_FOLDER = os.path.join('static', 'img', 'chapters')   # ⭐ NEW

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024                  # 5 MB — для обычных картинок
MAX_CHAPTER_UPLOAD = 300 * 1024 * 1024           # 300 MB — для загрузки главы


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
    """Состоит ли пользователь в команде (владелец или участник)."""
    if not user or not user.is_authenticated:
        return False
    if team.owner_id == user.id:
        return True
    return TeamMember.query.filter_by(team_id=team.id, user_id=user.id).first() is not None


def recalc_chapters_count(manga):
    """Обновляет manga.chapters_count = число уникальных номеров глав."""
    cnt = db.session.query(func.count(func.distinct(Chapter.number))).filter(
        Chapter.manga_id == manga.id
    ).scalar() or 0
    manga.chapters_count = cnt


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
            print('✅ База данных синхронизирована')

            if Manga.query.count() == 0:
                try:
                    from seed import seed_database
                    seed_database()
                    print('✅ База данных заполнена начальными данными')
                except Exception as e:
                    print(f'⚠️ Сидинг пропущен: {e}')

        except Exception as e:
            print(f'❌ Ошибка инициализации БД: {e}')


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'dev-secret-key-change-it'
    # ⭐ Поднимаем лимит для загрузки глав
    app.config['MAX_CONTENT_LENGTH'] = MAX_CHAPTER_UPLOAD

    base_dir = os.path.abspath(os.path.dirname(__name__))
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(base_dir, 'app.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    for folder in [UPLOAD_FOLDER, COVERS_FOLDER, AVATARS_FOLDER, BANNERS_FOLDER,
                   TEAMS_LOGOS_FOLDER, TEAMS_BANNERS_FOLDER, CHAPTERS_FOLDER]:
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
        popular_mangas = Manga.query.order_by(Manga.rating.desc()).limit(8).all()
        new_mangas = Manga.query.order_by(Manga.created_at.desc()).limit(6).all()
        genres = Genre.query.order_by(Genre.name).all()

        hero_blocks = HeroBlock.query.order_by(HeroBlock.position).all()
        if not hero_blocks:
            for i in range(1, 7):
                ext = 'jpg' if i in [1, 2] else 'png'
                default_block = HeroBlock(
                    position=i,
                    image_filename=f'block{i}.{ext}',
                    manga_id=i
                )
                db.session.add(default_block)
            db.session.commit()
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

    # ===================== РЕГИСТРАЦИЯ =====================
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

            flash('Вы успешно зарегистрировались!', 'success')
            login_user(new_user)
            return redirect(url_for('index'))

        return render_template('register.html')

    # ===================== ВХОД =====================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password_hash, password):
                flash('Неверное имя пользователя или пароль', 'error')
                return redirect(url_for('login'))

            login_user(user)
            return redirect(url_for('index'))

        return render_template('login.html')

    # ===================== ВЫХОД =====================
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'success')
        return redirect(url_for('index'))

    # ===================== КАТАЛОГ =====================
    @app.route('/catalog')
    def catalog():
        search_query = request.args.get('search', '')
        selected_genre = request.args.get('genre', '')

        manga_query = Manga.query
        if search_query:
            manga_query = manga_query.filter(
                Manga.title.like(f"%{search_query}%") |
                Manga.original_title.like(f"%{search_query}%")
            )
        if selected_genre:
            manga_query = manga_query.filter(Manga.genres.any(id=selected_genre))

        mangas = manga_query.order_by(Manga.rating.desc()).all()
        genres = Genre.query.all()
        return render_template('catalog.html',
                               mangas=mangas, genres=genres,
                               search_query=search_query,
                               selected_genre=selected_genre)

    # ===================== ДЕТАЛИ МАНГИ =====================
    @app.route('/manga/<int:manga_id>')
    def manga_detail(manga_id):
        manga = Manga.query.get_or_404(manga_id)
        library_entry = None
        if current_user.is_authenticated:
            library_entry = UserLibrary.query.filter_by(
                user_id=current_user.id, manga_id=manga_id
            ).first()

        comments = Comment.query.filter_by(manga_id=manga_id).order_by(Comment.created_at.desc()).all()

        # ⭐ Главы (сортировка: том → номер по убыванию)
        chapters = Chapter.query.filter_by(manga_id=manga_id) \
            .order_by(Chapter.volume.desc(), Chapter.number.desc()).all()

        # ⭐ Команды, от лица которых текущий пользователь может загружать главу
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
            # Оставляем только те, где манга есть в проектах
            user_teams_for_upload = [t for t in all_user_teams if manga in t.projects]

        return render_template('manga.html',
                               manga=manga,
                               library_entry=library_entry,
                               comments=comments,
                               chapters=chapters,
                               user_teams_for_upload=user_teams_for_upload)

    # ===================== ОБНОВЛЕНИЕ БИБЛИОТЕКИ =====================
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

    # ===================== КОММЕНТАРИИ =====================
    @app.route('/manga/<int:manga_id>/add_comment', methods=['POST'])
    @login_required
    def add_comment(manga_id):
        content = request.form.get('comment')
        if content:
            new_comment = Comment(
                user_id=current_user.id, manga_id=manga_id, content=content
            )
            db.session.add(new_comment)
            db.session.commit()
            flash('Комментарий опубликован!', 'success')
        return redirect(url_for('manga_detail', manga_id=manga_id))

    # ==================================================
    # ⭐⭐⭐ ГЛАВЫ И ФРЕЙМЫ ⭐⭐⭐
    # ==================================================

    # ---------- ДОБАВЛЕНИЕ ГЛАВЫ ----------
    @app.route('/teams/<slug>/manga/<int:manga_id>/chapters/add',
               methods=['GET', 'POST'])
    @login_required
    def chapter_add(slug, manga_id):
        team = TranslationTeam.query.filter_by(slug=slug).first_or_404()
        manga = Manga.query.get_or_404(manga_id)

        # Права: участник команды + манга в проектах команды
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

            # Уникальность главы
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

            # Создаём главу
            chapter = Chapter(
                manga_id=manga.id,
                team_id=team.id,
                uploader_id=current_user.id,
                volume=volume,
                number=number,
                title=title
            )
            db.session.add(chapter)
            db.session.flush()  # получим chapter.id

            # Каталог для фреймов
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
                    image_path=f'img/{rel_dir}/{unique_name}',  # путь относительно /static/
                    order=idx
                )
                db.session.add(frame)
                saved += 1

            if saved == 0:
                db.session.rollback()
                flash('Не удалось сохранить ни одного фрейма (проверьте формат файлов)', 'error')
                return redirect(request.url)

            # Обновляем счётчик глав в манге
            recalc_chapters_count(manga)
            if volume > (manga.volumes_count or 0):
                manga.volumes_count = volume

            db.session.commit()
            flash(f'Глава {chapter.display_number} успешно загружена ({saved} фреймов)', 'success')
            return redirect(url_for('manga_detail', manga_id=manga.id))

        return render_template('chapter_add.html', team=team, manga=manga)

    # ---------- ЧТЕНИЕ ГЛАВЫ ----------
    @app.route('/manga/<int:manga_id>/chapter/<int:chapter_id>')
    def chapter_read(manga_id, chapter_id):
        chapter = Chapter.query.get_or_404(chapter_id)
        if chapter.manga_id != manga_id:
            abort(404)

        chapter.views = (chapter.views or 0) + 1
        db.session.commit()

        # Соседние главы той же команды
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

    # ---------- УДАЛЕНИЕ ГЛАВЫ ----------
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
            # Удаляем файлы
            for frame in chapter.frames:
                abs_path = os.path.join('static', frame.image_path)
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                    except OSError as e:
                        print(f'Не удалось удалить файл {abs_path}: {e}')

            # Папка главы
            chapter_dir = os.path.join('static', 'img', 'chapters',
                                       str(chapter.manga_id),
                                       str(chapter.team_id),
                                       str(chapter.id))
            if os.path.isdir(chapter_dir):
                try:
                    # Удаляем оставшиеся файлы и саму папку
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

    # ---------- РЕДАКТИРОВАНИЕ МЕТАДАННЫХ ГЛАВЫ ----------
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
                # проверяем уникальность
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

    # ==================================================
    # АДМИН: ДОБАВИТЬ МАНГУ
    # ==================================================
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

    # ===================== АДМИН: HERO-БЛОКИ =====================
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

    # ===================== АДМИН: ОБЛОЖКА МАНГИ =====================
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

    # ===================== АДМИН: РЕДАКТИРОВАНИЕ МАНГИ =====================
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

    # ===================== АДМИН: УДАЛЕНИЕ МАНГИ =====================
    @app.route('/admin/manga/<int:manga_id>/delete', methods=['POST'])
    @admin_required
    def admin_delete_manga(manga_id):
        manga = Manga.query.get_or_404(manga_id)

        try:
            title = manga.title

            # ⭐ Удаляем все фреймы всех глав этой манги с диска
            for chapter in list(manga.chapters):
                for frame in chapter.frames:
                    abs_path = os.path.join('static', frame.image_path)
                    if os.path.exists(abs_path):
                        try:
                            os.remove(abs_path)
                        except OSError:
                            pass

            # Удаляем папку chapters/<manga_id>
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

    # ===================== АДМИН: СПИСОК ВСЕЙ МАНГИ =====================
    @app.route('/admin/mangas')
    @admin_required
    def admin_mangas():
        mangas = Manga.query.order_by(Manga.created_at.desc()).all()
        return render_template('admin_mangas.html', mangas=mangas)

    # ===================== БИБЛИОТЕКА =====================
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

    # ===================== ПРОФИЛЬ =====================
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

        return render_template('profile.html', user=user, stats=stats)

    # ===================== НАСТРОЙКИ =====================
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

    # ===================== КАТАЛОГ КОМАНД =====================
    @app.route('/teams')
    def teams_list():
        teams = TranslationTeam.query.order_by(TranslationTeam.created_at.desc()).all()
        return render_template('teams_list.html', teams=teams)

    # ===================== ЗАЯВКА НА СОЗДАНИЕ КОМАНДЫ =====================
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

    # ===================== МОИ ЗАЯВКИ =====================
    @app.route('/teams/my-applications')
    @login_required
    def my_team_applications():
        applications = TeamApplication.query.filter_by(
            user_id=current_user.id
        ).order_by(TeamApplication.created_at.desc()).all()
        return render_template('my_team_applications.html', applications=applications)

    # ===================== АДМИН: СПИСОК ЗАЯВОК =====================
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

    # ===================== АДМИН: ДЕТАЛИ ЗАЯВКИ =====================
    @app.route('/admin/team-applications/<int:app_id>')
    @admin_required
    def admin_team_application_detail(app_id):
        application = TeamApplication.query.get_or_404(app_id)
        return render_template('admin_team_application_detail.html', application=application)

    # ===================== АДМИН: ОДОБРИТЬ ЗАЯВКУ =====================
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

    # ===================== АДМИН: ОТКЛОНИТЬ ЗАЯВКУ =====================
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

    # ===================== СТРАНИЦА КОМАНДЫ =====================
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

    # ===================== РЕДАКТИРОВАНИЕ КОМАНДЫ =====================
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

    # ===================== ПРИГЛАШЕНИЕ В КОМАНДУ =====================
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

    # ===================== ОТВЕТ НА ПРИГЛАШЕНИЕ =====================
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

    # ===================== МОИ ПРИГЛАШЕНИЯ =====================
    @app.route('/invitations')
    @login_required
    def my_invitations():
        invitations = TeamInvitation.query.filter_by(
            user_id=current_user.id, status='PENDING'
        ).order_by(TeamInvitation.created_at.desc()).all()
        return render_template('my_invitations.html', invitations=invitations)

    # ===================== УДАЛЕНИЕ УЧАСТНИКА =====================
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

    # ===================== ДОБАВЛЕНИЕ ПРОЕКТА В КОМАНДУ =====================
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
                Manga.title.like(f"%{search_query}%") |
                Manga.original_title.like(f"%{search_query}%")
            )

        team_project_ids = [m.id for m in team.projects]
        if team_project_ids:
            mangas_query = mangas_query.filter(~Manga.id.in_(team_project_ids))

        all_mangas = mangas_query.order_by(Manga.title).limit(50).all()

        return render_template('team_add_project.html',
                               team=team,
                               mangas=all_mangas,
                               search_query=search_query)

    # ===================== УДАЛЕНИЕ ПРОЕКТА ИЗ КОМАНДЫ =====================
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

    # ===================== ФОРУМ =====================
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
        if topic.author_id != current_user.id and current_user.role != 'ADMIN':
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
        if post.author_id != current_user.id and current_user.role != 'ADMIN':
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
    @admin_required
    def forum_topic_toggle_pin(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)
        topic.is_pinned = not topic.is_pinned
        db.session.commit()
        flash('Закреплено' if topic.is_pinned else 'Откреплено', 'success')
        return redirect(url_for('forum_topic', topic_id=topic.id))

    @app.route('/forum/topic/<int:topic_id>/toggle-close', methods=['POST'])
    @admin_required
    def forum_topic_toggle_close(topic_id):
        topic = ForumTopic.query.get_or_404(topic_id)
        topic.is_closed = not topic.is_closed
        db.session.commit()
        flash('Тема закрыта' if topic.is_closed else 'Тема открыта', 'success')
        return redirect(url_for('forum_topic', topic_id=topic.id))

    # ===================== УВЕДОМЛЕНИЯ =====================
    @app.route('/notifications')
    @login_required
    def notifications():
        notifs = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(Notification.created_at.desc()).limit(50).all()

        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()

        return render_template('notifications.html', notifications=notifs)

    # ===================== CONTEXT PROCESSOR =====================
    @app.context_processor
    def inject_global_counts():
        counts = {
            'unread_notifications_count': 0,
            'pending_invitations_count': 0,
            'pending_team_apps_count': 0
        }

        if current_user.is_authenticated:
            try:
                counts['unread_notifications_count'] = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()

                counts['pending_invitations_count'] = TeamInvitation.query.filter_by(
                    user_id=current_user.id, status='PENDING'
                ).count()

                if current_user.role == 'ADMIN':
                    counts['pending_team_apps_count'] = TeamApplication.query.filter_by(
                        status='PENDING'
                    ).count()
            except Exception as e:
                print(f'Context processor error: {e}')

        return counts

    # ===================== АВТО-СОЗДАНИЕ ТАБЛИЦ =====================
    auto_update_database(app)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)