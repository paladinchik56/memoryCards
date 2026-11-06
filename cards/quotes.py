"""A small bank of quotes about learning and knowledge, shown one at a time
on the card list page. The same quote is shown to everyone all day and
changes the next day -- no database table needed for something this small.
"""
import hashlib
from datetime import date

QUOTES = [
    ("The beautiful thing about learning is that no one can take it away from you.", "B.B. King"),
    ("Live as if you were to die tomorrow. Learn as if you were to live forever.", "Mahatma Gandhi"),
    ("Education is not the filling of a pail, but the lighting of a fire.", "W.B. Yeats"),
    ("The capacity to learn is a gift; the ability to learn is a skill; the willingness to learn is a choice.", "Brian Herbert"),
    ("An investment in knowledge pays the best interest.", "Benjamin Franklin"),
    ("The more that you read, the more things you will know.", "Dr. Seuss"),
    ("Tell me and I forget, teach me and I may remember, involve me and I learn.", "Benjamin Franklin"),
    ("Learning never exhausts the mind.", "Leonardo da Vinci"),
    ("The expert in anything was once a beginner.", "Helen Hayes"),
    ("You don't have to be great to start, but you have to start to be great.", "Zig Ziglar"),
    ("Repetition is the mother of learning.", "Latin proverb"),
    ("Memory is the treasury and guardian of all things.", "Cicero"),
    ("A little progress each day adds up to big results.", "Unknown"),
    ("What we learn with pleasure we never forget.", "Alfred Mercier"),
    ("The only person who is educated is the one who has learned how to learn.", "Carl Rogers"),
    ("Change is the end result of all true learning.", "Leo Buscaglia"),
    ("I am always doing that which I cannot do, in order that I may learn how to do it.", "Pablo Picasso"),
    ("It is impossible for a man to learn what he thinks he already knows.", "Epictetus"),
    ("Knowledge is power.", "Francis Bacon"),
    ("By learning you will teach, by teaching you will learn.", "Latin proverb"),
]


def get_quote_of_the_day(today=None):
    """Pick one (text, author) pair, deterministically, from today's date.

    Deterministic (not `random.choice`) on purpose: everyone who opens the
    page today sees the same quote, and it only changes once the calendar
    date rolls over -- a real `random` pick would give a different quote on
    every single page load instead.
    """
    today = today or date.today()
    digest = hashlib.sha256(today.isoformat().encode()).hexdigest()
    index = int(digest, 16) % len(QUOTES)
    return QUOTES[index]
