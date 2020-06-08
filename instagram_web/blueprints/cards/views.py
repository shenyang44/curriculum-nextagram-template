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
    card_query = Card.select()
    cards = list(card_query)
    random.shuffle(cards)
    for i in range(len(cards)):
        cards[i].order = i
        cards[i].save()
    return render_template('cards/index.html', cards=cards)


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
    card_dict = {
        'description': card.description,
        'image_url': card.image_url,
        'order': card.order
    }
    if category == 'chance':
        emit('chance', json.dumps(card_dict))
    else:
        emit('community', json.dumps(card_dict))

    card.order += 5
    card.save()
