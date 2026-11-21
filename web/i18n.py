"""UI strings of the website (same wording as the mobile app). Templates use
`{{ t.key }}`; views use `tr(request, 'key', n=...)`. Add languages here."""

RU = {
    'tab_study': 'Учёба', 'tab_library': 'Библиотека', 'tab_profile': 'Профиль',

    'login_title': 'Вход', 'login_login': 'Ник или email', 'login_password': 'Пароль', 'login_submit': 'Войти',
    'login_failed': 'Неверный ник/email или пароль', 'login_no_account': 'Нет аккаунта?', 'login_register': 'Зарегистрироваться',
    'register_title': 'Регистрация', 'register_hint': 'Придумайте ник, укажите email и пароль — мы пришлём код подтверждения.',
    'register_submit': 'Получить код', 'register_have_account': 'Уже есть аккаунт?',
    'verify_title': 'Подтверждение email', 'verify_sent': 'Мы отправили код на', 'verify_submit': 'Подтвердить', 'verify_resend': 'Отправить код ещё раз',

    'study_in_blitz': 'в блитце', 'study_due': 'карточек ждут повторения', 'study_start': 'Начать блитц',
    'study_simple': 'Просто учёба', 'study_add': 'Добавить', 'study_all': 'Все карточки',

    'blitz_question': 'Вопрос', 'blitz_answer': 'Ответ', 'blitz_flip': 'Нажмите или пробел, чтобы перевернуть',
    'blitz_right': 'Верно', 'blitz_wrong': 'Неверно', 'blitz_keys': '← неверно · → верно',
    'blitz_empty': 'карточек, добавьте карточки в блитц', 'blitz_all_topics': 'Все темы', 'blitz_topics_n': 'Тем: {n}',
    'blitz_add': 'Карточка', 'blitz_remove': 'Из блитца', 'blitz_filter_hint': 'Только карточки блитца из выбранных тем',
    'blitz_show': 'Показать', 'blitz_undo': 'Отменить последний ответ', 'blitz_left': 'Осталось: {n}',

    'add_title': 'Добавить карточку', 'add_question': 'Вопрос', 'add_answer': 'Ответ', 'add_submit': 'Добавить',
    'add_no_topic': 'Без темы', 'add_topic': 'Тема', 'add_added': 'Добавлено в блитц',
    'add_duplicate': 'У вас уже есть карточка с таким вопросом', 'add_empty': 'Заполните вопрос и ответ',
    'latex_inline': 'в строке', 'latex_block': 'отдельной строкой',

    'cards_title': 'Карточки в блитце', 'cards_now': 'сейчас', 'cards_empty': 'В блитце пока нет карточек',
    'col_topic': 'Тема', 'col_question': 'Вопрос', 'col_answer': 'Ответ', 'col_next': 'Повтор через',

    'simple_title': 'Просто учёба', 'simple_no_topics': 'Нет тем. Создайте тему или добавьте чужую в библиотеке.',
    'simple_cards_n': 'Карточек: {n}', 'simple_status': 'Проход {round} · осталось {left}', 'simple_done': 'Пройдена ✓',
    'simple_continue_text': 'Вы остановились на проходе {round}. Осталось {left} из {total}.',
    'simple_continue': 'Продолжить с последнего места', 'simple_restart': 'Начать цикл заново',
    'simple_pass': 'Проход {n}', 'simple_pass_done': 'Проход {n} завершён', 'simple_right': 'верно',
    'simple_next': 'Следующий проход · {n}', 'simple_finish': 'Закончить', 'simple_topic_done': 'Тема пройдена — все ответы верные!',
    'simple_again': 'Начать заново', 'simple_empty': 'В теме нет карточек',

    'lib_title': 'Библиотека', 'lib_mine': 'Мои темы', 'lib_added': 'Добавленные темы', 'lib_browse': 'Смотреть библиотеку',
    'lib_browse_hint': 'Публичные темы всех пользователей', 'lib_topics_n': 'Тем: {n}', 'lib_no_topic': 'Без темы',
    'lib_cards_n': 'Карточек: {n}', 'lib_search': 'Название, описание, теги', 'lib_by': 'автор: {name}',
    'lib_new_topic': 'Новая тема', 'lib_edit_topic': 'Изменить тему', 'lib_edit': 'Изменить', 'lib_edit_deck': 'Редактировать колоду',
    'lib_select': 'Выбрать', 'lib_all': 'Все', 'lib_done': 'Готово', 'lib_to_blitz': 'В блитц', 'lib_copy': 'Копировать',
    'lib_move': 'Переместить', 'lib_from_deck': 'Из колоды', 'lib_delete': 'Удалить', 'lib_copy_to': 'Скопировать в тему',
    'lib_move_to': 'Переместить в тему', 'lib_no_own_topics': 'Сначала создайте свою тему в «Мои темы»',
    'lib_add_topic': 'Добавить тему себе', 'lib_remove_topic': 'Убрать из добавленных', 'lib_author_topics': 'Публичных тем: {n}',
    'lib_in_blitz': 'в блитце', 'lib_blitz_result': 'Добавлено: {added}. Сброшено: {reset}. Пропущено: {skipped}.',
    'lib_copied': 'Скопировано: {n}', 'lib_moved': 'Перемещено: {n}', 'lib_removed': 'Убрано из колоды: {n}',
    'lib_deleted': 'Удалено: {n}', 'lib_no_added': 'Пока нет добавленных тем. Найдите тему в «Смотреть библиотеку» и нажмите «Добавить тему себе».',
    'lib_empty_topic': 'В теме пока нет карточек', 'lib_nothing_found': 'Ничего не найдено', 'lib_share_link': 'Ссылка для доступа',
    'lib_copy_link': 'Скопировать', 'lib_pick_cards': 'Отметьте карточки', 'lib_delete_confirm': 'Удалить выбранные карточки совсем?',

    'topic_name': 'Название', 'topic_description': 'Описание', 'topic_tags': 'Теги через запятую', 'topic_visibility': 'Доступ',
    'topic_private': 'Приватная', 'topic_unlisted': 'По ссылке', 'topic_public': 'Публичная', 'topic_save': 'Сохранить',
    'topic_name_required': 'Введите название',

    'conflict_title': 'Уже в блитце: {n}', 'conflict_hint': 'Новых будет добавлено: {n}. Что сделать с остальными?',
    'conflict_skip': 'Пропустить', 'conflict_reset': 'Сбросить', 'conflict_all': 'Применить для всех карточек',
    'conflict_confirm': 'Добавить в блитц',

    'card_title': 'Карточка', 'card_save': 'Сохранить', 'card_saved': 'Сохранено',
    'card_status': 'В блитце · ступень {stage} · {when}', 'card_not_in_blitz': 'Не в блитце',
    'card_add_to_blitz': 'Добавить в блитц', 'card_reset': 'Сбросить прогресс', 'card_reset_confirm': 'Сбросить прогресс этой карточки?',
    'card_delete': 'Удалить карточку', 'card_delete_confirm': 'Удалить карточку совсем?', 'card_due_now': 'повтор сейчас',
    'card_due_in': 'повтор через {t}',

    'profile_in_blitz': 'в блитце', 'profile_learned': 'выучено', 'profile_streak': 'дней подряд', 'profile_study': 'Учёба',
    'profile_algorithm': 'Как работает повторение', 'profile_test_mode': 'Тестовый режим (повтор через 5 с)',
    'profile_app': 'Приложение', 'profile_language': 'Язык', 'profile_appearance': 'Оформление', 'profile_account': 'Аккаунт',
    'profile_nick_password': 'Ник и пароль', 'profile_export': 'Экспорт карточек', 'profile_logout': 'Выйти',
    'on': 'вкл', 'off': 'выкл',
    'appearance_system': 'Как в системе', 'appearance_light': 'Светлое', 'appearance_dark': 'Тёмное',

    'algo_title': 'Как работает повторение',
    'algo_intro': 'Каждая карточка в блитце стоит на одной из ступеней. Чем выше ступень, тем реже карточка повторяется.',
    'algo_stage': 'Ступень', 'algo_interval': 'Повтор через', 'algo_need': 'Верных для перехода', 'algo_max': 'максимум',
    'algo_rules': [
        'Верный ответ засчитывается на текущей ступени. Набрав нужное число верных ответов, карточка переходит на следующую ступень.',
        'Неверный ответ ничего не отнимает: ступень и засчитанные ответы сохраняются. Карточка вернётся в этой же сессии через 5–6 других.',
        'Выученная карточка (последняя ступень) остаётся в блитце и возвращается раз в месяц.',
        'Порядок случайный, но карточки, которые сильно просрочены относительно своей ступени, идут раньше.',
    ],

    'account_title': 'Ник и пароль', 'account_nickname': 'Ник', 'account_new_password': 'Новый пароль (необязательно)',
    'account_current': 'Текущий пароль', 'account_save': 'Сохранить', 'account_saved': 'Сохранено',
    'account_wrong': 'Неверный текущий пароль', 'account_taken': 'Этот ник уже занят',

    'back': 'Назад', 'close': 'Закрыть', 'cancel': 'Отмена',
    'time_s': '{n} с', 'time_m': '{n} мин', 'time_h': '{n} ч', 'time_d': '{n} дн', 'time_w': '{n} нед', 'time_mo': '{n} мес',
}

EN = {
    'tab_study': 'Study', 'tab_library': 'Library', 'tab_profile': 'Profile',

    'login_title': 'Log in', 'login_login': 'Nickname or email', 'login_password': 'Password', 'login_submit': 'Log in',
    'login_failed': 'Wrong nickname/email or password', 'login_no_account': 'No account?', 'login_register': 'Sign up',
    'register_title': 'Sign up', 'register_hint': "Pick a nickname, enter your email and a password — we'll send a confirmation code.",
    'register_submit': 'Get code', 'register_have_account': 'Already have an account?',
    'verify_title': 'Confirm email', 'verify_sent': 'We sent a code to', 'verify_submit': 'Confirm', 'verify_resend': 'Send the code again',

    'study_in_blitz': 'in blitz', 'study_due': 'cards due for review', 'study_start': 'Start blitz',
    'study_simple': 'Topic study', 'study_add': 'Add', 'study_all': 'All cards',

    'blitz_question': 'Question', 'blitz_answer': 'Answer', 'blitz_flip': 'Click or press Space to flip',
    'blitz_right': 'Right', 'blitz_wrong': 'Wrong', 'blitz_keys': '← wrong · → right',
    'blitz_empty': 'cards, add cards to the blitz', 'blitz_all_topics': 'All topics', 'blitz_topics_n': 'Topics: {n}',
    'blitz_add': 'Card', 'blitz_remove': 'From blitz', 'blitz_filter_hint': 'Only blitz cards from the chosen topics',
    'blitz_show': 'Show', 'blitz_undo': 'Undo last answer', 'blitz_left': 'Left: {n}',

    'add_title': 'Add card', 'add_question': 'Question', 'add_answer': 'Answer', 'add_submit': 'Add',
    'add_no_topic': 'No topic', 'add_topic': 'Topic', 'add_added': 'Added to the blitz',
    'add_duplicate': 'You already have a card with this question', 'add_empty': 'Fill in the question and the answer',
    'latex_inline': 'inline', 'latex_block': 'on its own line',

    'cards_title': 'Cards in the blitz', 'cards_now': 'now', 'cards_empty': 'No cards in the blitz yet',
    'col_topic': 'Topic', 'col_question': 'Question', 'col_answer': 'Answer', 'col_next': 'Next review in',

    'simple_title': 'Topic study', 'simple_no_topics': "No topics yet. Create one or add someone else's in the library.",
    'simple_cards_n': 'Cards: {n}', 'simple_status': 'Round {round} · {left} left', 'simple_done': 'Done ✓',
    'simple_continue_text': 'You stopped in round {round}. {left} of {total} left.',
    'simple_continue': 'Continue where I stopped', 'simple_restart': 'Start the cycle over',
    'simple_pass': 'Round {n}', 'simple_pass_done': 'Round {n} done', 'simple_right': 'right',
    'simple_next': 'Next round · {n}', 'simple_finish': 'Finish', 'simple_topic_done': 'Topic done — every answer right!',
    'simple_again': 'Start over', 'simple_empty': 'No cards in this topic',

    'lib_title': 'Library', 'lib_mine': 'My topics', 'lib_added': 'Added topics', 'lib_browse': 'Browse library',
    'lib_browse_hint': "Everyone's public topics", 'lib_topics_n': 'Topics: {n}', 'lib_no_topic': 'No topic',
    'lib_cards_n': 'Cards: {n}', 'lib_search': 'Name, description, tags', 'lib_by': 'by {name}',
    'lib_new_topic': 'New topic', 'lib_edit_topic': 'Edit topic', 'lib_edit': 'Edit', 'lib_edit_deck': 'Edit deck',
    'lib_select': 'Select', 'lib_all': 'All', 'lib_done': 'Done', 'lib_to_blitz': 'To blitz', 'lib_copy': 'Copy',
    'lib_move': 'Move', 'lib_from_deck': 'From deck', 'lib_delete': 'Delete', 'lib_copy_to': 'Copy to topic',
    'lib_move_to': 'Move to topic', 'lib_no_own_topics': 'Create a topic of your own in "My topics" first',
    'lib_add_topic': 'Add topic to mine', 'lib_remove_topic': 'Remove from added', 'lib_author_topics': 'Public topics: {n}',
    'lib_in_blitz': 'in blitz', 'lib_blitz_result': 'Added: {added}. Reset: {reset}. Skipped: {skipped}.',
    'lib_copied': 'Copied: {n}', 'lib_moved': 'Moved: {n}', 'lib_removed': 'Removed from deck: {n}',
    'lib_deleted': 'Deleted: {n}', 'lib_no_added': 'No added topics yet. Find one in "Browse library" and click "Add topic to mine".',
    'lib_empty_topic': 'No cards in this topic yet', 'lib_nothing_found': 'Nothing found', 'lib_share_link': 'Share link',
    'lib_copy_link': 'Copy', 'lib_pick_cards': 'Tick the cards', 'lib_delete_confirm': 'Delete the selected cards completely?',

    'topic_name': 'Name', 'topic_description': 'Description', 'topic_tags': 'Tags, comma-separated', 'topic_visibility': 'Access',
    'topic_private': 'Private', 'topic_unlisted': 'By link', 'topic_public': 'Public', 'topic_save': 'Save',
    'topic_name_required': 'Enter a name',

    'conflict_title': 'Already in the blitz: {n}', 'conflict_hint': 'New cards to add: {n}. What about the others?',
    'conflict_skip': 'Skip', 'conflict_reset': 'Reset', 'conflict_all': 'Apply to all cards', 'conflict_confirm': 'Add to blitz',

    'card_title': 'Card', 'card_save': 'Save', 'card_saved': 'Saved',
    'card_status': 'In blitz · stage {stage} · {when}', 'card_not_in_blitz': 'Not in the blitz',
    'card_add_to_blitz': 'Add to blitz', 'card_reset': 'Reset progress', 'card_reset_confirm': "Reset this card's progress?",
    'card_delete': 'Delete card', 'card_delete_confirm': 'Delete this card completely?', 'card_due_now': 'due now',
    'card_due_in': 'due in {t}',

    'profile_in_blitz': 'in blitz', 'profile_learned': 'learned', 'profile_streak': 'day streak', 'profile_study': 'Study',
    'profile_algorithm': 'How repetition works', 'profile_test_mode': 'Test mode (next review in 5 s)',
    'profile_app': 'App', 'profile_language': 'Language', 'profile_appearance': 'Appearance', 'profile_account': 'Account',
    'profile_nick_password': 'Nickname and password', 'profile_export': 'Export cards', 'profile_logout': 'Log out',
    'on': 'on', 'off': 'off',
    'appearance_system': 'System', 'appearance_light': 'Light', 'appearance_dark': 'Dark',

    'algo_title': 'How repetition works',
    'algo_intro': 'Every card in the blitz sits on a stage. The higher the stage, the less often the card comes back.',
    'algo_stage': 'Stage', 'algo_interval': 'Next review in', 'algo_need': 'Right answers to move up', 'algo_max': 'max',
    'algo_rules': [
        'A right answer counts on the current stage. Once a card has enough right answers, it moves up a stage.',
        'A wrong answer takes nothing away: stage and counted answers stay. The card comes back in the same session after 5–6 others.',
        'A learned card (last stage) stays in the blitz and comes back once a month.',
        'The order is random, but cards that are badly overdue for their stage go first.',
    ],

    'account_title': 'Nickname and password', 'account_nickname': 'Nickname', 'account_new_password': 'New password (optional)',
    'account_current': 'Current password', 'account_save': 'Save', 'account_saved': 'Saved',
    'account_wrong': 'Wrong current password', 'account_taken': 'This nickname is taken',

    'back': 'Back', 'close': 'Close', 'cancel': 'Cancel',
    'time_s': '{n}s', 'time_m': '{n} min', 'time_h': '{n} h', 'time_d': '{n} d', 'time_w': '{n} wk', 'time_mo': '{n} mo',
}

LANGUAGES = {'ru': ('Русский', RU), 'en': ('English', EN)}
assert set(RU) == set(EN), set(RU) ^ set(EN)


def get_language(request) -> str:
    lang = request.session.get('lang') if hasattr(request, 'session') else None
    if lang in LANGUAGES:
        return lang
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '').lower()
    return 'ru' if accept.startswith('ru') else 'en'


def strings(request) -> dict:
    return LANGUAGES[get_language(request)][1]


def tr(request, key, **params) -> str:
    text = strings(request)[key]
    for k, v in params.items():
        text = text.replace('{%s}' % k, str(v))
    return text


def format_duration(seconds: float, t: dict) -> str:
    """'25 min', '2 d'... (same rounding as the app)."""
    s = max(0, round(seconds))
    if s < 60:
        return t['time_s'].replace('{n}', str(s))
    m = round(s / 60)
    if m < 60:
        return t['time_m'].replace('{n}', str(m))
    h = round(m / 60)
    if h < 24:
        return t['time_h'].replace('{n}', str(h))
    d = round(h / 24)
    if d < 7:
        return t['time_d'].replace('{n}', str(d))
    if d < 30:
        return t['time_w'].replace('{n}', str(round(d / 7)))
    return t['time_mo'].replace('{n}', str(round(d / 30)))


def context(request):
    """Template context processor: `t` (strings), `lang`, `languages`."""
    return {
        't': strings(request),
        'lang': get_language(request),
        'languages': [(code, name) for code, (name, _) in LANGUAGES.items()],
    }
