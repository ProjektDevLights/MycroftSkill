from mycroft import MycroftSkill, intent_file_handler


class Devlight(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    @intent_file_handler('devlight.intent')
    def handle_devlight(self, message):
        self.speak_dialog('devlight')


def create_skill():
    return Devlight()

