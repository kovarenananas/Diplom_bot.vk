from random import randrange
import datetime
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

from database import Repository

with open('bot_token.txt', 'r') as file:
    bot_token = file.readline()
with open('user_token.txt', 'r') as file:
    user_token = file.readline()

vk = vk_api.VkApi(token=bot_token)
vk2 = vk_api.VkApi(token=user_token)
longpoll = VkLongPoll(vk)

IN_ACTIVE_SEARCH = 6
FEMALE = 1
MALE = 2


def get_user_info(user_id) -> dict:
    user_info = {}
    response = vk.method('users.get', {'user_id': user_id,
                                       'v': 5.131,
                                       'fields': 'fist_name, last_name, bdate, sex, city'})
    if response:
        for key, value in response[0].items():
            if key == 'city':
                user_info[key] = value['id']
            else:
                user_info[key] = value
    else:
        write_msg(user_id, 'Ошибка')
        return {}
    return user_info


def check_missing_info(user_info):
    info_missing = []
    for item in ['bdate', 'sex', 'city']:
        if not user_info.get(item):
            info_missing.append(item)
            continue
        if item == 'bdate':
            if len(user_info['bdate'].split('.')) != 3:
                info_missing.append('bdate')
        return info_missing


def write_msg(user_id, message, attachment=None):
    vk.method('messages.send', {'user_id': user_id,
                                'message': message,
                                'random_id': randrange(10 ** 7),
                                'attachment': attachment})


def get_additional_info(user_id, field):
    info_fields = {
        'bdate': 'дату рождения в формате XX.XX.XXXX',
        'city': 'в каком городе находитесь'}
    write_msg(user_id,
              f'''Нам нужно больше информации о вас, чтобы найти партнера. Пожалуйста, введи следующие данные: \n{info_fields[field]}''')
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if event.to_me:
                if field == 'city':
                    return get_city(user_id, event.text)
                elif field == 'bdate':
                    if len(event.text.split('.')) != 3:
                        # re.compile(\d{2}\.\d{2}\.\d{4})
                        write_msg(user_id, 'Неверно введена дата рождения')
                        return False
                    return event.text


def get_city(user_id, city):
    values = {
        'country_id': 1,
        'q': city,
        'count': 1
    }
    response = vk2.method('database.getCities', values=values)
    if response['items']:
        city_id = response['items'][0]['id']
        return city_id
    else:
        write_msg(user_id, 'Неверно указан город')
        return False


def get_age(date):
    return datetime.datetime.now().year - int(date[-4:])


def find_users(user_info, roma: Repository):
    response = vk2.method('users.search', {
        'age_from': user_info['age'] - 3,
        'age_to': user_info['age'] + 3,
        'sex': MALE if user_info['sex'] == FEMALE else FEMALE,
        'city': user_info['city'],
        'status': IN_ACTIVE_SEARCH,
        'has_photo': 1,
        'count': 1000,
        'v': 5.131})
    if response and response.get('items'):
        return [user_partner for user_partner in response.get('items')
                if not user_partner['is_closed'] and not roma.is_known_partner(user_info, user_partner)]
    write_msg(user_info['id'], 'Ошибка')
    return []


def get_photos(user_id) -> (bool, dict):
    """ Вернуть (успешно, фото)
        Если у человека есть хотя бы 3 фото в профиле
        Вернуть самые облайканные
    """
    try:
        response = vk2.method(
            'photos.get',
            {
                'owner_id': user_id,
                'album_id': 'profile',
                'extended': '1',
                'v': 5.131
            }
        )
        if response.get('count'):
            if response.get('count') < 3:
                return False, {}
            top_photos = sorted(
                response.get('items'),
                key=lambda x: x['likes']['count'] + x['comments']['count'],
                reverse=True,
            )[:3]
            photo_data = {'user_id': user_id, 'photo_ids': [photo['id'] for photo in top_photos]}
            return True, photo_data
        return False, {}
    except vk_api.exceptions.ApiError as error:
        print(error)
        return False, {}


def fill_missing_user_info(event, user_info):
    info_missing = check_missing_info(user_info)
    while info_missing:
        additional_info = get_additional_info(event.user_id, info_missing[0])
        if not additional_info:
            continue
        user_info[info_missing[0]] = additional_info
        info_missing.pop(0)


def main():
    with Repository() as roma:

        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_info = get_user_info(event.user_id)
                if not user_info:
                    continue
                write_msg(event.user_id,
                          f'''Привет, {user_info['first_name']}! Тебя приветствует бот для онлайн-знакомств VKinder.''')
                fill_missing_user_info(event, user_info)
                write_msg(event.user_id,
                          f'''Вся информация собрана, {user_info['first_name']}!''')
                user_info['age'] = get_age(user_info['bdate'])
                users_partners = find_users(user_info, roma)
                count_people = 5
                for partner in users_partners:
                    if count_people <= 0:
                        break
                    ok, chosen_photo = get_photos(partner['id'])
                    if ok:
                        count_people = count_people - 1
                        roma.insert_user_pair(user_info, partner)
                        beauty_text = f"{partner['first_name']} {partner['last_name']} https://vk.com/id{partner['id']}"
                        write_msg(event.user_id, beauty_text)
                        photo_massive = [f"photo{chosen_photo['user_id']}_{photo_id}"
                                         for photo_id in chosen_photo['photo_ids']]
                        write_msg(event.user_id, '', attachment=','.join(photo_massive))


if __name__ == '__main__':
    main()
