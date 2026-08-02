import os
import random
import json
import hashlib
import threading
import asyncio
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

app = Flask(__name__)
app.secret_key = 'supersecretkey_angelclub_2026'

# ===== ВСТРОЕННЫЕ ДАННЫЕ =====
BOT_TOKEN = "8844046364:AAEON7y5-NON7yLNVBV-RNnFHtqV95XGEhk"
ADMIN_ID = 8786313557
ADMIN_PASSWORD = "Pilot23411@"

# База данных Supabase (встроена в код)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:PilotMops23411@db.wipuqyayzezozioyfspm.supabase.co:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Папки для файлов
UPLOAD_FOLDER = 'static/uploads'
BALANCE_FOLDER = 'static/balance_checks'
ORDER_FOLDER = 'static/order_checks'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BALANCE_FOLDER'] = BALANCE_FOLDER
app.config['ORDER_FOLDER'] = ORDER_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BALANCE_FOLDER, exist_ok=True)
os.makedirs(ORDER_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ===== МОДЕЛИ =====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Integer, default=0)

class Anket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    price1 = db.Column(db.Integer, nullable=False)
    price3 = db.Column(db.Integer, nullable=False)
    price_night = db.Column(db.Integer, nullable=False)
    services = db.Column(db.String(200), nullable=False)
    extra_services = db.Column(db.Text, nullable=False, default='{}')
    description = db.Column(db.Text, nullable=False)
    photo_filename = db.Column(db.String(200), nullable=False)

class BalanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    check_filename = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('balance_requests', lazy=True))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anket_code = db.Column(db.String(6), nullable=False)
    duration = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    check_filename = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('orders', lazy=True))

with app.app_context():
    db.create_all()

def generate_code():
    while True:
        code = str(random.randint(100000, 999999))
        if not Anket.query.filter_by(code=code).first():
            
return code
# ===== МАРШРУТЫ САЙТА =====
@app.route('/')
def index():
    ankets = Anket.query.all()
    return render_template('index.html', ankets=ankets)

@app.route('/model/<code>')
def model_page(code):
    anket = Anket.query.filter_by(code=code).first()
    if not anket:
        flash('Модель не найдена')
        return redirect(url_for('index'))
    extra = json.loads(anket.extra_services) if anket.extra_services else {}
    return render_template('model_page.html', anket=anket, extra_services=extra)

@app.route('/order/<code>', methods=['GET', 'POST'])
def order(code):
    if 'user_id' not in session:
        flash('Сначала войдите')
        return redirect(url_for('login', next=request.url))
    anket = Anket.query.filter_by(code=code).first()
    if not anket:
        flash('Модель не найдена')
        return redirect(url_for('index'))
    extra_total = request.args.get('extra', 0, type=int)
    if request.method == 'POST':
        duration = request.form.get('duration')
        if duration not in ['1h', '3h', 'night']:
            flash('Выберите длительность')
            return redirect(request.url)
        if duration == '1h':
            base_amount = anket.price1
        elif duration == '3h':
            base_amount = anket.price3
        else:
            base_amount = anket.price_night
        extra = request.form.get('extra', 0, type=int)
        amount = base_amount + extra
        file = request.files.get('check_photo')
        if not file or not allowed_file(file.filename):
            flash('Загрузите фото чека (jpg, png, gif)')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        filename = f"order_{code}_{session['user_id']}_{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(app.config['ORDER_FOLDER'], filename))
        new_order = Order(
            user_id=session['user_id'], anket_code=code, duration=duration,
            amount=amount, check_filename=filename, status='pending'
        )
        db.session.add(new_order)
        db.session.commit()
        flash('✅ Ваш заказ отправлен на проверку. Администрация разбирается, ждите подтверждения.')
        return redirect(url_for('my_orders'))
    duration_prices = {'1h': anket.price1, '3h': anket.price3, 'night': anket.price_night}
    return render_template('order.html', anket=anket, duration_prices=duration_prices, extra_total=extra_total)

@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session:
        flash('Сначала войдите')
        return redirect(url_for('login', next=request.url))
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    for order in orders:
        anket = Anket.query.filter_by(code=order.anket_code).first()
        order.model_name = anket.name if anket else 'Удалена'
        order.duration_label = {'1h': '1 час', '3h': '3 часа', 'night': 'Ночь'}.get(order.duration, order.duration)
        status_map = {'pending': '⏳ Ожидает подтверждения', 'approved': '✅ Подтверждён', 'rejected': '❌ Отклонён'}
        order.status_label = status_map.get(order.status, order.status)
    return render_template('my_orders.html', orders=orders)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            flash('Введите код модели')
            return render_template('search.html')
        anket = Anket.query.filter_by(code=code).first()
        if anket:
            return redirect(url_for('model_page', code=code))
        else:
            flash('Модель с таким кодом не найдена')
            return render_template('search.html')
    return render_template('search.html')

@app.route('/balance', methods=['GET', 'POST'])
def balance():
    if 'user_id' not in session:
        flash('Сначала войдите')
        return redirect(url_for('login', next=request.url))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        amount = request.form.get('amount')
        file = request.files.get('check_photo')
        if not amount or not file:
            flash('Заполните все поля и загрузите фото чека')
            return redirect(url_for('balance'))
        if not allowed_file(file.filename):
            flash('Неподдерживаемый формат файла')
            return redirect(url_for('balance'))
        filename = secure_filename(file.filename)
        filename = f"user_{user.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        file.save(os.path.join(app.config['BALANCE_FOLDER'], filename))
        new_req = BalanceRequest(user_id=user.id, amount=int(amount), check_filename=filename, status='pending')
        db.session.add(new_req)
        db.session.commit()
        flash('✅ Ваш чек отправлен на проверку. Администратор свяжется с вами.')
        return redirect(url_for('balance'))
    return render_template('balance.html', user=user)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/support')
def support():
    return render_template('support.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_page = request.args.get('next')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Заполните все поля')
            return render_template('register.html', next=next_page)
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html', next=next_page)
        new_user = User(username=username, password_hash=hash_password(password))
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна! Теперь войдите.')
        return redirect(url_for('login', next=next_page))
    return render_template('register.html', next=next_page)

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next')
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password_hash == hash_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Вход выполнен')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
    return render_template('login.html', next=next_page)

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли')
    return redirect(url_for('login'))
  @app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_authorized'] = True
            flash('Добро пожаловать в админ-панель!')
            return redirect(url_for('admin'))
        else:
            flash('Неверный пароль!')
            return render_template('admin_login.html')
    if session.get('admin_authorized'):
        all_ankets = Anket.query.order_by(Anket.id.desc()).all()
        return render_template('admin.html', ankets=all_ankets)
    else:
        return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_authorized', None)
    flash('Вы вышли из админ-панели')
    return redirect(url_for('index'))

@app.route('/panel', methods=['GET', 'POST'])
def panel():
    if 'user_id' not in session:
        flash('Сначала войдите в аккаунт')
        return redirect(url_for('login', next=request.url))
    user_id = session['user_id']
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            name = request.form['name']
            age = int(request.form['age'])
            if age < 18 or age > 60:
                flash('❌ Возраст должен быть от 18 до 60 лет.')
                return redirect(url_for('panel'))
            city = request.form['city']
            price1 = int(request.form['price1'])
            if price1 < 1500 or price1 > 700000:
                flash('❌ Цена за 1 час должна быть от 1500 до 700 000 ₽.')
                return redirect(url_for('panel'))
            price3 = int(request.form['price3'])
            if price3 < 1500 or price3 > 700000:
                flash('❌ Цена за 3 часа должна быть от 1500 до 700 000 ₽.')
                return redirect(url_for('panel'))
            price_night = int(request.form['price_night'])
            if price_night < 1500 or price_night > 700000:
                flash('❌ Цена за ночь должна быть от 1500 до 700 000 ₽.')
                return redirect(url_for('panel'))
            services = ', '.join(request.form.getlist('services'))
            description = request.form['description']
            file = request.files['photo']
            extra_services = {}
            extra_names = request.form.getlist('extra_name')
            extra_prices = request.form.getlist('extra_price')
            for n, p in zip(extra_names, extra_prices):
                if n and p:
                    try:
                        extra_services[n] = int(p)
                    except:
                        pass
            if file and allowed_file(file.filename):
                code = generate_code()
                filename = secure_filename(file.filename)
                filename = f"{code}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_anket = Anket(
                    code=code, user_id=user_id, name=name, age=age, city=city,
                    price1=price1, price3=price3, price_night=price_night,
                    services=services, description=description,
                    photo_filename=filename,
                    extra_services=json.dumps(extra_services, ensure_ascii=False)
                )
                db.session.add(new_anket)
                db.session.commit()
                flash(f'✅ Анкета создана! Код: {code}')
            else:
                flash('❌ Ошибка загрузки фото')
            return redirect(url_for('panel'))
        elif action == 'delete':
            code = request.form.get('code')
            if session.get('admin_authorized'):
                anket = Anket.query.filter_by(code=code).first()
            else:
                anket = Anket.query.filter_by(code=code, user_id=user_id).first()
            if anket:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], anket.photo_filename))
                except:
                    pass
                db.session.delete(anket)
                db.session.commit()
                flash(f'✅ Анкета {code} удалена')
            else:
                flash('❌ Анкета не найдена или не принадлежит вам')
            return redirect(url_for('panel'))
        elif action == 'approve_order':
            order_id = int(request.form.get('order_id'))
            order = Order.query.get(order_id)
            if order:
                order.status = 'approved'
                db.session.commit()
                flash(f'✅ Заказ #{order_id} подтверждён')
            else:
                flash('❌ Заказ не найден')
            return redirect(url_for('panel'))
        elif action == 'reject_order':
            order_id = int(request.form.get('order_id'))
            order = Order.query.get(order_id)
            if order:
                order.status = 'rejected'
                db.session.commit()
                flash(f'✅ Заказ #{order_id} отклонён')
            else:
                flash('❌ Заказ не найден')
            return redirect(url_for('panel'))
    if session.get('admin_authorized'):
        ankets = Anket.query.filter_by(user_id=user_id).all()
    else:
        ankets = Anket.query.filter_by(user_id=user_id).all()
    orders = Order.query.filter_by(status='pending').all()
    for order in orders:
        anket = Anket.query.filter_by(code=order.anket_code).first()
        order.model_name = anket.name if anket else 'Удалена'
        order.duration_label = {'1h': '1 час', '3h': '3 часа', 'night': 'Ночь'}.get(order.duration, order.duration)
    return render_template('panel.html', ankets=ankets, orders=orders)

@app.route('/edit/<code>', methods=['GET', 'POST'])
def edit_anket(code):
    if 'user_id' not in session and not session.get('admin_authorized'):
        flash('Сначала войдите')
        return redirect(url_for('login', next=request.url))
    if session.get('admin_authorized'):
        anket = Anket.query.filter_by(code=code).first()
    else:
        anket = Anket.query.filter_by(code=code, user_id=session['user_id']).first()
    if not anket:
        flash('Анкета не найдена или не принадлежит вам')
        return redirect(url_for('panel' if not session.get('admin_authorized') else 'admin'))
    if request.method == 'POST':
        name = request.form['name']
        age = int(request.form['age'])
        if age < 18 or age > 60:
            flash('❌ Возраст должен быть от 18 до 60 лет.')
            return redirect(request.url)
        city = request.form['city']
        price1 = int(request.form['price1'])
        if price1 < 1500 or price1 > 700000:
            flash('❌ Цена за 1 час должна быть от 1500 до 700 000 ₽.')
            return redirect(request.url)
        price3 = int(request.form['price3'])
        if price3 < 1500 or price3 > 700000:
            flash('❌ Цена за 3 часа должна быть от 1500 до 700 000 ₽.')
            return redirect(request.url)
        price_night = int(request.form['price_night'])
        if price_night < 1500 or price_night > 700000:
            flash('❌ Цена за ночь должна быть от 1500 до 700 000 ₽.')
            return redirect(request.url)
        anket.name = name
        anket.age = age
        anket.city = city
        anket.price1 = price1
        anket.price3 = price3
        anket.price_night = price_night
        anket.services = ', '.join(request.form.getlist('services'))
        anket.description = request.form['description']
        extra_services = {}
        extra_names = request.form.getlist('extra_name')
        extra_prices = request.form.getlist('extra_price')
        for n, p in zip(extra_names, extra_prices):
            if n and p:
                try:
                    extra_services[n] = int(p)
                except:
                    pass
        anket.extra_services = json.dumps(extra_services, ensure_ascii=False)
        file = request.files.get('photo')
        if file and allowed_file(file.filename):
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], anket.photo_filename))
            except:
                pass
            filename = secure_filename(file.filename)
            filename = f"{anket.code}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            anket.photo_filename = filename
        db.session.commit()
        flash(f'✅ Анкета {code} обновлена')
        if session.get('admin_authorized'):
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('panel'))
    services_list = ['МБР', 'Минет', 'Анал', 'Классический секс', 'Массаж', 'Стриптиз',
                     'Ролевые игры', 'БДСМ', 'Фетиш', 'Лесби-шоу']
    selected_services = anket.services.split(', ') if anket.services else []
    extra = json.loads(anket.extra_services) if anket.extra_services else {}
    extra_items = list(extra.items()) if extra else []
    return render_template(
        'edit_anket.html', anket=anket, services_list=services_list,
        selected=selected_services, extra_items=extra_items
          )
              # ============================================================
# TELEGRAM БОТ
# ============================================================
NAME, AGE, CITY, DESCRIPTION, PRICE1, PRICE3, PRICE_NIGHT, SERVICES, PHOTO = range(9)

async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("➕ Добавить анкету", callback_data="add_profile")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот Angel Club.\nНажми кнопку, чтобы добавить анкету на сайт:",
        reply_markup=reply_markup,
    )

async def add_profile_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите имя модели:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введите возраст (18–60):")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 18 or age > 60:
            await update.message.reply_text("Возраст должен быть от 18 до 60. Попробуй снова:")
            return AGE
        context.user_data["age"] = age
        await update.message.reply_text("Введите город:")
        return CITY
    except ValueError:
        await update.message.reply_text("Введи число. Сколько лет модели?")
        return AGE

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text
    await update.message.reply_text("Введите описание (о себе):")
    return DESCRIPTION

async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("Цена за 1 час (₽):")
    return PRICE1

async def get_price1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["price1"] = int(update.message.text)
        await update.message.reply_text("Цена за 3 часа (₽):")
        return PRICE3
    except ValueError:
        await update.message.reply_text("Цифрами, пожалуйста:")
        return PRICE1

async def get_price3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["price3"] = int(update.message.text)
        await update.message.reply_text("Цена за ночь (₽):")
        return PRICE_NIGHT
    except ValueError:
        await update.message.reply_text("Цифрами, пожалуйста:")
        return PRICE3

async def get_price_night(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["price_night"] = int(update.message.text)
        await update.message.reply_text("Услуги через запятую (например: Массаж, Минет):")
        return SERVICES
    except ValueError:
        await update.message.reply_text("Цифрами, пожалуйста:")
        return PRICE_NIGHT

async def get_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["services"] = update.message.text
    await update.message.reply_text("Отправь ОДНО фото модели:")
    return PHOTO

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file = await update.message.photo[-1].get_file()
    photo_url = photo_file.file_path
    photo_bytes = await photo_file.download_as_bytearray()
    with app.app_context():
        bot_user = User.query.filter_by(username="telegram_bot").first()
        if not bot_user:
            bot_user = User(username="telegram_bot", password_hash="bot", balance=0)
            db.session.add(bot_user)
            db.session.commit()
        code = generate_code()
        filename = f"{code}_bot.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, "wb") as f:
            f.write(photo_bytes)
        new_anket = Anket(
            code=code, user_id=bot_user.id, name=context.user_data["name"],
            age=context.user_data["age"], city=context.user_data["city"],
            price1=context.user_data["price1"], price3=context.user_data["price3"],
            price_night=context.user_data["price_night"],
            services=context.user_data["services"],
            description=context.user_data["description"],
            photo_filename=filename, extra_services='{}'
        )
        db.session.add(new_anket)
        db.session.commit()
    await update.message.reply_text(f"✅ Анкета создана!\nКод: {code}\nОна сразу появилась на сайте.")
    keyboard = [[InlineKeyboardButton("🗑 Удалить анкету", callback_data=f"delete_{code}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 Новая анкета из бота!\n\nКод: {code}\n"
             f"Имя: {context.user_data['name']}, {context.user_data['age']}\n"
             f"Город: {context.user_data['city']}\n"
             f"1ч: {context.user_data['price1']}₽ | 3ч: {context.user_data['price3']}₽ | Ночь: {context.user_data['price_night']}₽\n"
             f"Услуги: {context.user_data['services']}",
        reply_markup=reply_markup,
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_url)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Напиши /start чтобы начать заново.")
    return ConversationHandler.END

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, code = data.split("_", 1)
    with app.app_context():
        anket = Anket.query.filter_by(code=code).first()
        if not anket:
            await query.edit_message_text("Анкета уже удалена.")
            return
        if action == "delete":
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], anket.photo_filename))
            except:
                pass
            db.session.delete(anket)
            db.session.commit()
            await query.edit_message_text(f"❌ Анкета {code} удалена.")

def run_bot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_profile_button, pattern="^add_profile$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            PRICE1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price1)],
            PRICE3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price3)],
            PRICE_NIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_price_night)],
            SERVICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_services)],
            PHOTO: [MessageHandler(filters.PHOTO, get_photo)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(CommandHandler("start", bot_start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^delete_"))
    application.run_polling()

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
  
