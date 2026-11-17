"""Create the public demo topic "Электротехника" (30 cards) for a given user.

Idempotent: running it again only adds cards that are missing.
Usage: python manage.py seed_electrical [--owner NICKNAME]
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Profile
from cards.models import Card, Collection

NAME = 'Электротехника'
DESCRIPTION = ('Основные законы и формулы электротехники: постоянный ток, конденсаторы, '
               'электромагнетизм, переменный ток.')

CARDS = [
    ('Закон Ома для участка цепи', 'I = U / R'),
    ('Закон Ома для полной цепи', 'I = ε / (R + r)\nε — ЭДС источника, r — его внутреннее сопротивление'),
    ('Первый закон Кирхгофа', 'Сумма токов в узле равна нулю: ΣI = 0\n(сколько тока втекает в узел, столько и вытекает)'),
    ('Второй закон Кирхгофа', 'В замкнутом контуре сумма ЭДС равна сумме падений напряжения: ΣE = Σ(I·R)'),
    ('Сопротивление проводника через его размеры', 'R = ρ·l / S\nρ — удельное сопротивление, l — длина, S — площадь сечения'),
    ('Зависимость сопротивления от температуры', 'R = R₀·(1 + α·Δt)\nα — температурный коэффициент сопротивления'),
    ('Последовательное соединение резисторов', 'R = R₁ + R₂ + …\nТок через все резисторы одинаковый'),
    ('Параллельное соединение резисторов', '1/R = 1/R₁ + 1/R₂ + …\nНапряжение на всех резисторах одинаковое'),
    ('Мощность постоянного тока', 'P = U·I = I²·R = U²/R'),
    ('Закон Джоуля — Ленца', 'Q = I²·R·t\nКоличество теплоты, выделяемое током в проводнике'),
    ('Работа электрического тока', 'A = U·I·t'),
    ('Ёмкость конденсатора (определение)', 'C = q / U'),
    ('Ёмкость плоского конденсатора', 'C = ε₀·ε·S / d\nS — площадь пластин, d — расстояние между ними'),
    ('Энергия заряженного конденсатора', 'W = C·U² / 2'),
    ('Последовательное соединение конденсаторов', '1/C = 1/C₁ + 1/C₂ + …'),
    ('Параллельное соединение конденсаторов', 'C = C₁ + C₂ + …'),
    ('Закон Кулона', 'F = k·|q₁·q₂| / r²\nk ≈ 9·10⁹ Н·м²/Кл²'),
    ('Закон электромагнитной индукции (Фарадея)', 'ε = −N·ΔΦ / Δt\nЭДС индукции пропорциональна скорости изменения магнитного потока'),
    ('Правило Ленца', 'Индукционный ток направлен так, чтобы своим магнитным полем противодействовать изменению магнитного потока, которое его вызвало'),
    ('Сила Ампера', 'F = B·I·l·sin α\nСила, действующая на проводник с током в магнитном поле'),
    ('Сила Лоренца', 'F = q·v·B·sin α\nСила, действующая на движущийся заряд в магнитном поле'),
    ('Магнитный поток', 'Φ = B·S·cos α'),
    ('ЭДС самоиндукции', 'ε = −L·ΔI / Δt'),
    ('Энергия магнитного поля катушки', 'W = L·I² / 2'),
    ('Индуктивное сопротивление', 'X_L = ω·L = 2π·f·L'),
    ('Ёмкостное сопротивление', 'X_C = 1 / (ω·C) = 1 / (2π·f·C)'),
    ('Полное сопротивление последовательной RLC-цепи', 'Z = √(R² + (X_L − X_C)²)'),
    ('Действующее значение синусоидального тока', 'I = I_m / √2 ≈ 0,707·I_m\nI_m — амплитудное значение'),
    ('Активная, реактивная и полная мощность', 'P = U·I·cos φ (Вт)\nQ = U·I·sin φ (вар)\nS = U·I = √(P² + Q²) (В·А)'),
    ('Коэффициент трансформации трансформатора', 'k = U₁ / U₂ = N₁ / N₂ = I₂ / I₁'),
]
assert len(CARDS) == 30


class Command(BaseCommand):
    help = 'Create the public demo topic "Электротехника" (30 cards).'

    def add_arguments(self, parser):
        parser.add_argument('--owner', default='admin', help='Nickname of the owner (default: admin)')

    def handle(self, *args, owner, **options):
        profile = Profile.objects.filter(nickname__iexact=owner).select_related('user').first()
        if profile is None:
            raise CommandError(f'No user with nickname "{owner}".')
        user = profile.user
        collection, created = Collection.objects.get_or_create(
            owner=user, name=NAME,
            defaults={'description': DESCRIPTION, 'visibility': Collection.VISIBILITY_PUBLIC},
        )
        existing = set(Card.objects.filter(user=user).values_list('question', flat=True))
        new = [Card(user=user, question=q, answer=a, collection=collection) for q, a in CARDS if q not in existing]
        Card.objects.bulk_create(new)
        self.stdout.write(f'{"Created" if created else "Updated"} "{NAME}": +{len(new)} cards, '
                          f'{collection.cards.count()} total, share token {collection.share_token}')
