from collections import namedtuple

"""
A notification to be sent at a relative time after the member has started playing the game.
"""
RelativeNotification = namedtuple("RelativeNotification", "minutes message")

FACTORIO_RELATIVE_NOTIFICATIONS = [
    RelativeNotification(
        60,
        "You've been playing Factorio for over an hour. Perhaps stretch your legs and grab a cup of tea?",
    ),
    RelativeNotification(
        120,
        "You've been playing Factorio for over two hours. It might be time for a break?",
    ),
    RelativeNotification(
        150,
        "I'd strongly recommend stepping away from squishing biters for a bit.",
    ),
    RelativeNotification(
        180,
        "You've now been playing Factorio for over three hours. I'd strongly suggest untangling those spaghetti conveyor belts another time.",
    ),
    RelativeNotification(
        210,
        "Reminder: You're a human, not a construction robot. Stand up, breathe, recalibrate.",
    ),
    RelativeNotification(
        240,
        "You've been playing Factorio for over four hours. Your factory is not more important than your spine. Take a break.",
    ),
]
