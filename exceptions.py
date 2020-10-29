class Impossible(Exception):
    """Exception rased when an action is impossible to perform
    reason given as the exception message"""


class QuitWithoutSaving(SystemExit):
    """can be raised to exit the game without automatically saving"""
