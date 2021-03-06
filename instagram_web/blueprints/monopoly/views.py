from flask import Blueprint, render_template, request, flash,  redirect, url_for
from flask_login import current_user, login_user, login_required
from models.user import User
from models.properties import Property
from models.activity_log import ActivityLog
from models.cards import Card
from app import socketio
from flask_socketio import send, emit
import json
from instagram_web.blueprints.cards.views import shuffle, draw_card
import math


monopoly_blueprint = Blueprint(
    'monopoly', __name__, template_folder='templates')


def update_activities():
    activities = ActivityLog.select().order_by(
        ActivityLog.created_at.desc())
    activity_text = [x.text for x in activities]
    dictionary = {'activities': activity_text}
    data = json.dumps(dictionary)
    socketio.emit('activity_update', data)


def update_positions():
    users = User.select().where((User.monopoly > 0) & (
        User.username != 'Banker')).order_by(User.created_at.desc())
    user_dict = []
    locations = ['Go', 'Old Kent Road', 'Community Chest', 'Whitechapel Road', 'Income Tax', "King's Cross Station", 'The Angel Islington', 'Chance', 'Euston Road', 'Pentonville Road', 'Jail', 'Pall Mall', 'Electric Company', 'Whitehall', 'Northumberland Ave.', 'Marylebone Station', 'Bow Street', 'Community Chest 2', 'Marlborough Street',
                 'Vine Street', 'Free Parking', 'Strand', 'Chance 2', 'Fleet Street', 'Trafalgar Square', 'Fenchurch St. Station', 'Leicester Square', 'Coventry Street', 'Water Works', 'Piccadilly', 'Go to Jail!', 'Regent Street', 'Oxford Street', 'Community Chest 3', 'Bond Street', 'Liverpool St. Station', 'Chance 3', 'Park Lane', 'Supertax', 'Mayfair']

    for user in users:
        position = locations[user.position]
        if position == 'Jail' and user.jailed < 0:
            position = 'Visiting jail'
        user_dict.append({
            'username': user.username,
            'position': position,
            'money': user.money
        })
    user_json = json.dumps(user_dict)
    socketio.emit('position_update', user_json)


def activity_create(txt):
    new_activity = ActivityLog(text=txt)
    new_activity.save()
    activities = ActivityLog.select()
    if len(activities) > 8:
        new_activities = ActivityLog.select().order_by(
            ActivityLog.created_at.desc()).limit(8)
        old_activities = ActivityLog.select().where(
            ActivityLog.id.not_in([activity.id for activity in new_activities]))
        for old_act in old_activities:
            old_act.delete_instance()
    update_activities()
    update_positions()


def update_jailed():
    user = {
        'jailed': current_user.jailed,
        'freedom_cost': math.ceil(current_user.wealth * 0.05)
    }
    data = json.dumps(user)
    emit('jail_update', data)


def jail_free():
    current_user.jailed = -1
    current_user.doubles = 0
    current_user.save()


@socketio.on('user_request')
def update_users():
    users = User.select().where(User.monopoly > 0).order_by(User.created_at.desc())
    users_usernames = []
    for user in users:
        if user.username != current_user.username:
            users_usernames.append(user.username)
    emit('users_info', users_usernames)


@socketio.on('connect')
def handle_connection():
    update_positions()
    update_activities()
    update_users()
    update_jailed()
    if len(current_user.card) > 0:
        card = current_user.card[0]
        if not card.activated:
            emit('card_drawn')


@socketio.on('money_request')
def money_show():
    if current_user.is_authenticated:
        emit('money_update', current_user.money)


@monopoly_blueprint.route('/')
def index():
    if current_user.is_authenticated:
        users = User.select().where((User.monopoly > 0) & (User.username != 'Banker'))
        properties = Property.select()
        return render_template('monopoly/index1.html', properties=properties, users=users)

    else:
        flash('login is required', 'danger')
        return redirect(url_for('users.index'))


@monopoly_blueprint.route('/create')
def create():
    user = User.get_or_none(User.id == current_user.id)
    if user.monopoly > 0:
        user.monopoly = 0
    else:
        user.monopoly = 1

    if user.save():
        flash('updated successfully', 'success')
    else:
        flash('failwhale', 'danger')

    return redirect(url_for('users.index'))


def go_and_jail_check():
    if current_user.position > 39:
        current_user.position = current_user.position - 40
        current_user.money += 200
        current_user.save()
        return('passed go')

    if current_user.position == 30:
        current_user.position = 10
        current_user.jailed = 0
        current_user.doubles = 0
        current_user.save()
        return('in jail')


@socketio.on('jail_pay')
def jail_pay(cost):
    if current_user.is_authenticated:
        current_user.money -= int(cost)
        jail_free()
        update_jailed()
        if not current_user.save():
            send('jail payment could not be done for some reason.')
        else:
            activity_create(
                f'{current_user.username} payed ${cost} to get out of jail.')
    else:
        flash('need to be signed in to perform this action!', 'warning')
        return redirect(url_for('users.index'))


@socketio.on('roll')
def roll(data):
    if len(current_user.card) > 0:
        user_card = Card.get_or_none(Card.user_id == current_user.id)
        user_card.user_id = None
        user_card.alternative_img = None
        user_card.activated = False
        user_card.save()

    roll_data = json.loads(data)
    roll_0 = roll_data['roll1']
    roll_1 = roll_data['roll2']
    jail_roll = int(roll_data['jail roll'])
    roll_sum = int(roll_0) + int(roll_1)
    text = f'{current_user.username} rolled {roll_0} & {roll_1}. '

    if jail_roll > 0:
        if roll_0 == roll_1:
            jail_free()
            text += 'Thus escaping jail. '
        elif current_user.jailed == 2:
            cost = math.ceil(current_user.wealth * 0.05)
            current_user.money -= cost
            jail_free()
            text += f'Got out of jail by paying ${cost}.'
        else:
            current_user.jailed += 1
            activity_create(
                f'{text} Thus failing to get out of jail.')
            current_user.save()
            # early return to prevent position change.
            return
    elif roll_0 == roll_1:
        current_user.doubles += 1
    else:
        current_user.doubles = 0

    current_user.position += roll_sum
    if current_user.doubles == 3:
        current_user.position = 30

    current_user.save()

    gajc_return = go_and_jail_check()
    if gajc_return == 'passed go':
        text += 'Passed go and collected $200'
    elif gajc_return == 'in jail':
        text += 'And ended up in jail.'

    if current_user.position in (7, 22, 36):
        draw_card('chance')
    elif current_user.position in (2, 17, 33):
        draw_card('community')

    activity_create(text)
    update_jailed()


@monopoly_blueprint.route('/reset')
def reset():
    if current_user.is_authenticated and (current_user.username == 'Banker' or current_user.username == 'shennex'):
        banker = User.get_or_none(User.username == 'Banker')

        users_update = User.update(jailed=-1, position=0, money=1500, doubles=0,).where(
            (User.monopoly > 0) & (User.username != 'Banker'))
        users_update.execute()

        prop_update = Property.update(
            houses=0, mortgaged=False, user_id=banker.id)
        prop_update.execute()

        banker.money = 1000000
        banker.save()
        deletion = ActivityLog.delete().where(ActivityLog.text != '')
        deletion.execute()

        shuffle()

        return redirect(request.referrer)
    else:
        flash('no access for u, soz', 'danger')
        return(redirect(url_for('users.index')))


@socketio.on('pay')
def pay(data):
    if current_user.is_authenticated:
        pay_data = json.loads(data)
        recipient_username = pay_data['recipient']
        amount = pay_data['amount']
        recipient = User.get_or_none(User.username == recipient_username)
        amount = int(amount)
        if amount > current_user.money:
            send('broke')
            return

        current_user.money -= amount
        recipient.money += amount

        if current_user.save() and recipient.save():
            activity_create(
                f'{current_user.username} payed ${amount} to {recipient_username}')
        else:
            print('failed saving at pay func.')


@socketio.on('wealth_request')
def wealth_index():
    users = User.select().where((User.monopoly > 0) & (User.username != 'Banker'))
    wealth_list = []
    for user in users:
        wealth_list.append(
            f'{user.username} has a total wealth of ${user.wealth}')
    emit('wealth_show', wealth_list)


@monopoly_blueprint.route('/eww')
def puzzle():
    return render_template('monopoly/puzzle.html')
