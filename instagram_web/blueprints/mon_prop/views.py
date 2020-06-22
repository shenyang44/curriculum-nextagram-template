from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from models.user import User
from models.properties import Property
from werkzeug.utils import secure_filename
from config import S3_BUCKET, S3_LOCATION
from helpers import upload_file_to_s3
from app import socketio
from flask_socketio import send, emit
import json
from instagram_web.blueprints.monopoly.views import activity_create

mon_prop_blueprint = Blueprint(
    'mon_prop', __name__, template_folder='templates')


@mon_prop_blueprint.route('/update')
def update():
    if current_user.username == 'Banker':
        properties = Property.select().order_by(Property.created_at)
        return render_template('mon_prop/update.html', properties=properties)
    else:
        flash('no access 4 u', 'danger')
        return redirect(url_for('monopoly.index'))


@mon_prop_blueprint.route('/edit', methods=['POST'])
def edit():
    if current_user.username == 'Banker':
        prop_name = request.form.get('prop_name')
        prop_price = request.form.get('price_input')
        prop = Property.get_or_none(Property.name == prop_name)
        if not prop:
            flash('no such property', 'danger')
            return redirect(request.referrer)

        prop.price = prop_price
        if prop.save():
            flash('saved successfully', 'success')
        else:
            flash('problem saving', 'warning')
        return redirect(request.referrer)
    else:
        flash('sorry, but you do not have access to this', 'warning')
        return redirect(url_for('monopoly.index'))


@mon_prop_blueprint.route('/new')
def new():
    if current_user.username == 'Banker':
        return render_template('mon_prop/new.html')
    else:
        flash('sorry, but you do not have access to that feature!', 'danger')
        return redirect(url_for('monopoly.index'))


@mon_prop_blueprint.route('/create', methods=['POST'])
def create():
    if current_user.username == 'Banker':
        name = request.form.get('name')
        house_price = request.form.get('house-price')
        category = request.form.get('category')
        if house_price == '':
            house_price = 0

        if "image-file" not in request.files:
            flash("No file was chosen! :O", 'warning')
            return redirect(request.referrer)
        file = request.files.get('image-file')
        file_name = secure_filename(file.filename)
        img_upload_err = str(upload_file_to_s3(file, S3_BUCKET))
        new_prop = Property(name=name, user_id=current_user.id,
                            house_price=house_price, category=category, image=file_name)
        if new_prop.save():
            flash('new property was saved', 'success')
            return redirect(url_for('mon_prop.new'))
        else:
            flash(f'failed, {img_upload_err}', 'danger')
            return redirect(request.referrer)


@socketio.on('prop_request')
def prop_show(username, house=False):
    if current_user.is_authenticated:
        user = User.get_or_none(User.username == str(username))
        if not user:
            print('no such user')
            return
        owned_props = Property.select().where(
            Property.user_id == user.id).order_by(Property.created_at.desc())

        prop_data = []
        for each in owned_props:
            image_url = each.image_url
            house_price = each.house_price
            houses = each.houses
            name = each.name
            prop_data.append({
                'name': name,
                'houses': houses,
                'house_price': house_price,
                'image_url': image_url
            })

        prop_dict = {
            'username': user.username,
            'values': prop_data,
            'house': house
        }
        data = json.dumps(prop_dict)
        emit('prop_response', data)


@socketio.on('house edit')
def house_create(prop_name, sell=False):
    if current_user.is_authenticated:
        current_prop = Property.get_or_none(Property.name == prop_name)
        if not current_prop:
            print('not prop')
            return
        if current_prop.user_id != current_user.id:
            print('not user')
            return

        if sell:
            if current_prop.houses < 1:
                print('prop has no houses')
                send('no house')
            else:
                current_user.money += (current_prop.house_price * 0.5)
                current_prop.houses -= 1
                activity_create(
                    f'{current_user.username} sold a house at {prop_name} | ${int(current_prop.house_price * 0.5)}')
        else:
            if current_user.money < current_prop.house_price:
                print('broke')
                send('broke')
            else:
                current_user.money -= current_prop.house_price
                current_prop.houses += 1
                activity_create(
                    f'{current_user.username} bought a house for {prop_name} | ${current_prop.house_price}')

        if not current_prop.save():
            print('prop did not save')
        if not current_user.save():
            print('user did not save')

        emit('house update', prop_name, current_prop.houses)


@socketio.on('house sell')
@socketio.on('prop_transfer')
def prop_edit(recipient_username, prop_name):
    prop_to_transfer = Property.get_or_none(Property.name == prop_name)
    recipient = User.get_or_none(User.username == recipient_username)
    if not prop_to_transfer:
        send('no such property')
        return
    if not recipient:
        send('no such user')
        return

    prop_to_transfer.user_id = recipient.id
    if prop_to_transfer.save():
        activity_create(
            f'{recipient_username} received {prop_name} from {current_user.username}')
    else:
        send('property.save failed')
