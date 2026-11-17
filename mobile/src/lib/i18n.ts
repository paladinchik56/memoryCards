/** UI strings. Every user-visible text goes through `t()`; add languages here. */

const ru = {
  'tab.study': 'Учёба',
  'tab.library': 'Библиотека',
  'tab.profile': 'Профиль',

  'login.title': 'Вход',
  'login.server': 'Адрес сервера',
  'login.login': 'Ник или email',
  'login.password': 'Пароль',
  'login.submit': 'Войти',
  'login.failed': 'Неверный ник/email или пароль',
  'login.network': 'Сервер недоступен. Проверьте адрес и что телефон в той же сети.',

  'study.inBlitz': '{n} в блитце',
  'study.dueCaption': 'карточек ждут повторения',
  'study.start': 'Начать блитц',
  'study.simple': 'Просто учёба',
  'study.add': 'Добавить',
  'study.all': 'Все карточки',
  'study.simpleSoon': 'Просто учёба появится в следующей версии.',

  'blitz.question': 'Вопрос',
  'blitz.answer': 'Ответ',
  'blitz.tapToFlip': 'Нажмите, чтобы перевернуть',
  'blitz.right': 'Верно',
  'blitz.wrong': 'Неверно',
  'blitz.swipeHint': '← неверно · верно →',
  'blitz.empty': 'карточек, добавьте карточки в блитц',
  'blitz.allTopics': 'Все темы',
  'blitz.topicsN': 'Тем: {n}',
  'blitz.addCard': 'Карточка',
  'blitz.filterTitle': 'Учить темы',
  'blitz.filterHint': 'Только карточки блитца из выбранных тем',
  'blitz.show': 'Показать',

  'add.title': 'Добавить карточку',
  'add.question': 'Вопрос',
  'add.answer': 'Ответ',
  'add.submit': 'Добавить',
  'add.noTopic': 'Без темы',
  'add.added': 'Добавлено в блитц',
  'add.duplicate': 'У вас уже есть карточка с таким вопросом',
  'add.empty': 'Заполните вопрос и ответ',
  'add.chooseTopic': 'Тема',

  'cards.title': 'Карточки в блитце',
  'cards.now': 'сейчас',
  'cards.empty': 'В блитце пока нет карточек',

  'lib.title': 'Библиотека',
  'lib.mine': 'Мои темы',
  'lib.added': 'Добавленные темы',
  'lib.browse': 'Смотреть библиотеку',
  'lib.browseHint': 'Публичные темы всех пользователей',
  'lib.topicsN': 'Тем: {n}',
  'lib.noTopic': 'Без темы',
  'lib.cardsN': 'Карточек: {n}',
  'lib.addedSoon': 'Добавленные темы появятся в следующей версии.',
  'lib.search': 'Название или описание',
  'lib.offline': 'Нет связи с сервером',
  'lib.by': 'автор: {name}',
  'lib.addToBlitz': 'Добавить в блитц ({n})',
  'lib.addedResult': 'Добавлено: {added}. Уже были: {skipped}.',
  'lib.yours': 'Это ваша тема',
  'lib.questionCol': 'Вопрос',
  'lib.answerCol': 'Ответ',
  'lib.emptyTopic': 'В теме пока нет карточек',

  'profile.synced': 'Синхронизация: {when}',
  'profile.never': 'ещё не было',
  'profile.syncing': 'Синхронизация…',
  'profile.syncError': 'Нет связи с сервером',
  'profile.refresh': 'Обновить',
  'profile.inBlitz': 'в блитце',
  'profile.learned': 'выучено',
  'profile.streak': 'дней подряд',
  'profile.study': 'Учёба',
  'profile.algorithm': 'Как работает повторение',
  'profile.reminder': 'Напоминание о блитце',
  'profile.app': 'Приложение',
  'profile.language': 'Язык',
  'profile.appearance': 'Оформление',
  'profile.account': 'Аккаунт',
  'profile.nickPassword': 'Ник и пароль',
  'profile.export': 'Экспорт карточек',
  'profile.logout': 'Выйти',
  'profile.logoutConfirm': 'Выйти? Неотправленные изменения будут потеряны.',
  'profile.soon': 'скоро',
  'appearance.system': 'Как в системе',
  'appearance.light': 'Светлое',
  'appearance.dark': 'Тёмное',

  'algo.title': 'Как работает повторение',
  'algo.intro': 'Каждая карточка в блитце стоит на одной из ступеней. Чем выше ступень, тем реже карточка повторяется.',
  'algo.stage': 'Ступень',
  'algo.interval': 'Повтор через',
  'algo.need': 'Верных для перехода',
  'algo.max': 'максимум',
  'algo.rules':
    '• Верный ответ засчитывается на текущей ступени. Набрав нужное число верных ответов, карточка переходит на следующую ступень.\n' +
    '• Неверный ответ ничего не отнимает: ступень и засчитанные ответы сохраняются. Карточка вернётся в этой же сессии через 5–6 других.\n' +
    '• Выученная карточка (последняя ступень) остаётся в блитце и возвращается раз в месяц.\n' +
    '• Порядок случайный, но карточки, которые сильно просрочены относительно своей ступени, идут раньше.',

  'common.cancel': 'Отмена',
  'common.ok': 'OK',
  'common.close': 'Закрыть',
  'time.s': '{n} с',
  'time.m': '{n} мин',
  'time.h': '{n} ч',
  'time.d': '{n} дн',
  'time.w': '{n} нед',
  'time.mo': '{n} мес',
  'time.ago': '{t} назад',
  'time.justNow': 'только что',
};

type Key = keyof typeof ru;

const en: Record<Key, string> = {
  'tab.study': 'Study',
  'tab.library': 'Library',
  'tab.profile': 'Profile',

  'login.title': 'Log in',
  'login.server': 'Server address',
  'login.login': 'Nickname or email',
  'login.password': 'Password',
  'login.submit': 'Log in',
  'login.failed': 'Wrong nickname/email or password',
  'login.network': "Can't reach the server. Check the address and that the phone is on the same network.",

  'study.inBlitz': '{n} in blitz',
  'study.dueCaption': 'cards due for review',
  'study.start': 'Start blitz',
  'study.simple': 'Topic study',
  'study.add': 'Add',
  'study.all': 'All cards',
  'study.simpleSoon': 'Topic study is coming in the next version.',

  'blitz.question': 'Question',
  'blitz.answer': 'Answer',
  'blitz.tapToFlip': 'Tap to flip',
  'blitz.right': 'Right',
  'blitz.wrong': 'Wrong',
  'blitz.swipeHint': '← wrong · right →',
  'blitz.empty': 'cards, add cards to the blitz',
  'blitz.allTopics': 'All topics',
  'blitz.topicsN': 'Topics: {n}',
  'blitz.addCard': 'Card',
  'blitz.filterTitle': 'Study topics',
  'blitz.filterHint': 'Only blitz cards from the chosen topics',
  'blitz.show': 'Show',

  'add.title': 'Add card',
  'add.question': 'Question',
  'add.answer': 'Answer',
  'add.submit': 'Add',
  'add.noTopic': 'No topic',
  'add.added': 'Added to the blitz',
  'add.duplicate': 'You already have a card with this question',
  'add.empty': 'Fill in the question and the answer',
  'add.chooseTopic': 'Topic',

  'cards.title': 'Cards in the blitz',
  'cards.now': 'now',
  'cards.empty': 'No cards in the blitz yet',

  'lib.title': 'Library',
  'lib.mine': 'My topics',
  'lib.added': 'Added topics',
  'lib.browse': 'Browse library',
  'lib.browseHint': "Everyone's public topics",
  'lib.topicsN': 'Topics: {n}',
  'lib.noTopic': 'No topic',
  'lib.cardsN': 'Cards: {n}',
  'lib.addedSoon': 'Added topics are coming in the next version.',
  'lib.search': 'Name or description',
  'lib.offline': "Can't reach the server",
  'lib.by': 'by {name}',
  'lib.addToBlitz': 'Add to blitz ({n})',
  'lib.addedResult': 'Added: {added}. Already had: {skipped}.',
  'lib.yours': 'This is your topic',
  'lib.questionCol': 'Question',
  'lib.answerCol': 'Answer',
  'lib.emptyTopic': 'No cards in this topic yet',

  'profile.synced': 'Synced: {when}',
  'profile.never': 'never',
  'profile.syncing': 'Syncing…',
  'profile.syncError': "Can't reach the server",
  'profile.refresh': 'Refresh',
  'profile.inBlitz': 'in blitz',
  'profile.learned': 'learned',
  'profile.streak': 'day streak',
  'profile.study': 'Study',
  'profile.algorithm': 'How repetition works',
  'profile.reminder': 'Blitz reminder',
  'profile.app': 'App',
  'profile.language': 'Language',
  'profile.appearance': 'Appearance',
  'profile.account': 'Account',
  'profile.nickPassword': 'Nickname and password',
  'profile.export': 'Export cards',
  'profile.logout': 'Log out',
  'profile.logoutConfirm': 'Log out? Unsynced changes will be lost.',
  'profile.soon': 'soon',
  'appearance.system': 'System',
  'appearance.light': 'Light',
  'appearance.dark': 'Dark',

  'algo.title': 'How repetition works',
  'algo.intro': 'Every card in the blitz sits on a stage. The higher the stage, the less often the card comes back.',
  'algo.stage': 'Stage',
  'algo.interval': 'Next review in',
  'algo.need': 'Right answers to move up',
  'algo.max': 'max',
  'algo.rules':
    '• A right answer counts on the current stage. Once a card has enough right answers, it moves up a stage.\n' +
    '• A wrong answer takes nothing away: stage and counted answers stay. The card comes back in the same session after 5–6 others.\n' +
    '• A learned card (last stage) stays in the blitz and comes back once a month.\n' +
    '• The order is random, but cards that are badly overdue for their stage go first.',

  'common.cancel': 'Cancel',
  'common.ok': 'OK',
  'common.close': 'Close',
  'time.s': '{n}s',
  'time.m': '{n} min',
  'time.h': '{n} h',
  'time.d': '{n} d',
  'time.w': '{n} wk',
  'time.mo': '{n} mo',
  'time.ago': '{t} ago',
  'time.justNow': 'just now',
};

export const LANGUAGES = { ru: 'Русский', en: 'English' } as const;
export type Language = keyof typeof LANGUAGES;
const TABLES: Record<Language, Record<Key, string>> = { ru, en };

export type T = (key: Key, params?: Record<string, string | number>) => string;

export function translator(lang: Language): T {
  return (key, params) => {
    let s = TABLES[lang][key] ?? ru[key] ?? key;
    if (params) for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
}

/** "25 min", "2 d"... for a duration in ms. */
export function formatDuration(ms: number, t: T): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return t('time.s', { n: s });
  const m = Math.round(s / 60);
  if (m < 60) return t('time.m', { n: m });
  const h = Math.round(m / 60);
  if (h < 24) return t('time.h', { n: h });
  const d = Math.round(h / 24);
  if (d < 7) return t('time.d', { n: d });
  if (d < 30) return t('time.w', { n: Math.round(d / 7) });
  return t('time.mo', { n: Math.round(d / 30) });
}
