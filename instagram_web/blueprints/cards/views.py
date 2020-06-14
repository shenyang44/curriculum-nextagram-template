from flask import request, redirect, url_for, render_template, flash, Blueprint
from models.cards import Card
import json
from flask_socketio import send, emit
from app import socketio
from flask_login import current_user
from models.user import User
from werkzeug.utils import secure_filename
from helpers import upload_file_to_s3
from config import S3_BUCKET
import random


cards_blueprint = Blueprint('cards', __name__, template_folder='templates')


@cards_blueprint.route('/new')
def new():
    return render_template('cards/new.html')


@cards_blueprint.route('/create', methods=['POST'])
def create():
    description = request.form.get('description')
    category = request.form.get('category')

    if 'image-file' not in request.files:
        flash('no file was chosen!', 'warning')
        return redirect(request.referrer)
    file = request.files.get('image-file')
    file_name = secure_filename(file.filename)
    img_upload_err = str(upload_file_to_s3(file, S3_BUCKET))
    new_card = Card(description=description,
                    category=category, image=file_name)

    if new_card.save():
        flash('new card was saved', 'success')
    else:
        flash(f'saving failed, {img_upload_err}', 'danger')

    return redirect(request.referrer)


@cards_blueprint.route('/')
def index():
    cards = Card.select()
    return render_template('cards/index.html', cards=cards)


@socketio.on('shuffle_cards')
def shuffle():
    card_query = Card.select()
    for card in card_query:
        card.order = None
        card.save()
    cards = list(card_query)
    random.shuffle(cards)
    for i in range(len(cards)):
        cards[i].order = i
        cards[i].save()


def draw_card(category):
    if category == 'chance':
        cards = Card.select().where(Card.category == 'chance').order_by(Card.order).limit(1)
    else:
        cards = Card.select().where(Card.category == 'community').order_by(Card.order).limit(1)
    card = cards[0]

    users = User.select().where(
        (User.monopoly > 0) & (User.username != 'Banker'))
    wealthiest_user = users[0]

    for user in users:
        if user.wealth > wealthiest_user.wealth:
            wealthiest_user = user

    if card.description == 'poor tax' and user.username == wealthiest_user.username:
        card.alternative_img = 'https://nextagram-shen.s3.amazonaws.com/poor-tax-rich.jpg'
    if card.description == 'doc fee':
        poorest_user = users[0]
        for user in users:
            if user.wealth < poorest_user.wealth:
                poorest_user = user

        if user.id == wealthiest_user.id:
            card.alternative_img = 'https://nextagram-shen.s3.amazonaws.com/doc-fee-1.jpg'
        elif user.id == poorest_user.id:
            card.alternative_img = 'https://nextagram-shen.s3.amazonaws.com/doc-fee-3.jpg'

    card.save()
    image_url = card.image_url
    if card.alternative_img is not None:
        image_url = card.alternative_img

    card_dict = {
        'description': card.description,
        'image_url': image_url,
        'order': card.order
    }

    emit('card_drawn', json.dumps(card_dict))

    card.user_id = current_user.id
    card.order += 32
    card.save()


@socketio.on('view_card')
def show(username):
    user = User.get_or_none(User.username == username)

    if not user:
        print('no such user in card.show')
        send('View card, user get error, contact shen')
        return
    card = Card.get_or_none(Card.user_id == user.id)

    if not card:
        print('no such user in card.show')
        send('View card error, contact shen')
        return

    image_url = card.image_url
    if card.alternative_img is not None:
        image_url = card.alternative_img

    card_dict = {
        'image_url': image_url,
        'category': card.category
    }
    emit('card_show', json.dumps(card_dict))


@socketio.on('card_effect')
def card_effect():
    from instagram_web.blueprints.monopoly.views import update_positions
    if not current_user.is_authenticated:
        flash('You need to be logged in!', 'danger')
        return redirect(url_for('users.index'))

    card = Card.get_or_none(Card.user_id == current_user.id)
    if not card:
        send('no card found! seek help')
        return

    if card.description == 'go to jail':
        current_user.position = 10
        current_user.jailed = 0
        current_user.doubles = 0
    elif card.description == 'go back 3':
        current_user.position -= 3
    elif card.description == 'go to go':
        current_user.position = 0
        current_user.money += 200
    elif card.description == 'go to kings':
        current_user.money += 200
        current_user.position = 5
    elif card.description == 'go to mayfair':
        current_user.position = 39
    elif card.description == 'go to pall':
        if current_user.position > 11:
            current_user.money += 200
        current_user.position = 11
    elif card.description == 'go to railway':
        if current_user.position == 36:
            current_user.position = 5
            current_user.money += 200
        elif current_user.position == 22:
            current_user.position = 25
        else:
            current_user.positon = 15
    elif card.description == 'go to trafalgar':
        if current_user.position > 24:
            current_user.money += 200
        current_user.positon = 24
    elif card.description == 'nearest util':
        if current_user.posiiton == 33:
            current_user.money += 200
        if current_user.position == 22:
            current_user.position = 28
        else:
            current_user.posiiton = 12
    card.activated = True
    card.save()
    current_user.save()
    update_positions()
