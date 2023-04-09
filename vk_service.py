from random import randrange

from vk_api import vk_api
from vk_api.longpoll import VkLongPoll

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
REQUEST_SIZE = 50


def get_user_info(user_id) -> dict:
    """ Собираем инфо о пользователе, который ищет партнеров"""
    user_info = {}
    response = vk.method('users.get', {'user_id': user_id,
                                       'v': 5.131,
                                       'fields': 'fist_name, last_name, bdate, sex, city'})
    try:
        if response:
            for key, value in response[0].items():
                if key == 'city':
                    user_info[key] = value['id']
                else:
                    user_info[key] = value
        else:
            write_msg(user_id, 'Ошибка. Не смогли получить информацию о пользователе')
            return {}
        return user_info
    except vk_api.exceptions.ApiError as error:
        print(error)
        return {}


def write_msg(user_id, message, attachment=None):
    """Пишем сообщение в диалог с пользователем"""
    vk.method('messages.send', {'user_id': user_id,
                                'message': message,
                                'random_id': randrange(10 ** 7),
                                'attachment': attachment})

def get_city_id(user_id, city):
    """Запрашиваем ID города пользователя"""
    values = {
        'country_id': 1,
        'q': city,
        'count': 1
    }
    try:
        response = vk2.method('database.getCities', values=values)
        if response['items']:
            city_id = response['items'][0]['id']
            return city_id
        else:
            write_msg(user_id, 'Неверно указан город')
            return None
    except vk_api.exceptions.ApiError as error:
        print(error)
        return None

def find_users(user_info, offset: int, roma: Repository):
    """ Найти информацию о потенциальных партнерах
    """
    try:
        response = vk2.method('users.search', {
            'age_from': user_info['age'] - 3,
            'age_to': user_info['age'] + 3,
            'sex': MALE if user_info['sex'] == FEMALE else FEMALE,
            'city': user_info['city'],
            'status': IN_ACTIVE_SEARCH,
            'has_photo': 1,
            'count': REQUEST_SIZE,
            'offset': offset,
            'v': 5.131})
        if response and response.get('items'):
            return [user_partner for user_partner in response.get('items')
                    if not user_partner['is_closed'] and not roma.is_known_partner(user_info, user_partner)]
        write_msg(user_info['id'], 'Ошибка. Партнеры не найдены')
        return []
    except vk_api.exceptions.ApiError as error:
        print(error)
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
