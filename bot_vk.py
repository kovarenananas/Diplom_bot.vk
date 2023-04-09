import datetime
from vk_api.longpoll import VkEventType

from database import Repository
from vk_service import get_user_info, write_msg, find_users, get_city_id, get_photos, longpoll, REQUEST_SIZE


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


def get_additional_info(user_id, field):
    info_fields = {
        'bdate': 'дату рождения в формате XX.XX.XXXX',
        'city': 'в каком городе находитесь'}
    write_msg(user_id,
              f'''Нам нужно больше информации о вас, чтобы найти партнера. Пожалуйста, введите следующие данные: \n{info_fields[field]}''')
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if event.to_me:
                if field == 'city':
                    return get_city_id(user_id, event.text)
                elif field == 'bdate':
                    if len(event.text.split('.')) != 3:
                        # re.compile(\d{2}\.\d{2}\.\d{4})
                        write_msg(user_id, 'Неверно введена дата рождения')
                        return False
                    return event.text


def get_age(date):
    return datetime.datetime.now().year - int(date[-4:])


def fill_missing_user_info(event, user_info):
    info_missing = check_missing_info(user_info)
    while info_missing:
        additional_info = get_additional_info(event.user_id, info_missing[0])
        if not additional_info:
            continue
        user_info[info_missing[0]] = additional_info
        info_missing.pop(0)


def init_partners_buffer(event, roma, state_bot):
    if state_bot['offset'] != 0:
        state_bot['offset'] = 0
        state_bot['partners_buffer'] = []
    request_new_users(roma, state_bot)
    write_msg(event.user_id, 'Список партнеров готов, для просмотра анкет нажмите "Далее"')


def show_next_partner(event, roma, state_bot):
    buffer = state_bot['partners_buffer']
    found_ok_partner = False
    while not found_ok_partner:
        if not buffer:
            request_new_users(roma, state_bot)
            buffer = state_bot['partners_buffer']
        chosen_partner = buffer.pop(0)
        ok, chosen_photo = get_photos(chosen_partner['id'])
        if ok:
            found_ok_partner = True
            roma.insert_user_pair(state_bot['user_data'], chosen_partner)
            beauty_text = f"{chosen_partner['first_name']} {chosen_partner['last_name']} https://vk.com/id{chosen_partner['id']}"
            write_msg(event.user_id, beauty_text)
            photo_massive = [f"photo{chosen_photo['user_id']}_{photo_id}"
                             for photo_id in chosen_photo['photo_ids']]
            write_msg(event.user_id, '', attachment=','.join(photo_massive))


def request_new_users(roma, state_bot):
    users_partners = find_users(state_bot['user_data'], state_bot['offset'], roma)
    state_bot['partners_buffer'] = users_partners
    state_bot['offset'] += REQUEST_SIZE


def prepare_user_info(event) -> dict | None:
    user_info = get_user_info(event.user_id)
    if not user_info:
        return None
    write_msg(event.user_id,
              f'''Привет, {user_info['first_name']}! Тебя приветствует бот для онлайн-знакомств VKinder.''')
    fill_missing_user_info(event, user_info)
    user_info['age'] = get_age(user_info['bdate'])
    write_msg(event.user_id,
              f'''Вся информация собрана, {user_info['first_name']}!''')
    write_msg(event.user_id,
              'Для взаимодействия с ботом используйте компанды "Поиск" и "Далее". '
              f'"Поиск" запустит поиск партнеров, "Далее" покажет следующего кандидата, {user_info["first_name"]}!')
    return user_info


def main():
    with Repository() as roma:
        state_bot = {
            "user_data": None,
            "offset": 0,
            "partners_buffer": []
        }
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                if state_bot['user_data'] is None:
                    state_bot['user_data'] = prepare_user_info(event)
                    continue

                answer_from_user = event.text.lower()
                if state_bot['user_data'] is not None and answer_from_user == 'поиск':
                    init_partners_buffer(event, roma, state_bot)

                if state_bot['user_data'] is not None and answer_from_user == 'далее':
                    show_next_partner(event, roma, state_bot)


if __name__ == '__main__':
    main()
