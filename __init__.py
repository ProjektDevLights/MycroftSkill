import json
import re
from os import nice, path

import requests
from adapt.intent import IntentBuilder
from colour import Color
from mycroft import MycroftSkill, intent_handler


class Devlight(MycroftSkill):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json"}
    patterns = ["plain", "gradient", "runner",
                "fading", "rainbow", "single color", "two colors", "party", "running"]

    def __init__(self):
        MycroftSkill.__init__(self)
        lights = requests.get("http://devlight.local/lights")
        self.headers
        self.lights = lights.json()["object"]
        self.light_names = [l["name"].lower() for l in lights.json()["object"]]

    @intent_handler(IntentBuilder("").require("light").one_of("on", "off").build())
    def handle_devlight_power(self, message):
        text = message.data.get("utterance").lower()
        name = next((name for name in self.light_names if name in text), None)
        status = message.data.get("on")
        if status == None:
            status = "off"
        if name == None:
            name = self.promptName()

        self.lightPower(name, status)

    @intent_handler(IntentBuilder("").require("lights").require("all").one_of("on", "off").build())
    def handle_all_power(self, message):
        status = message.data.get("on")
        if status == None:
            status = "off"
        for l in self.light_names:
            self.lightPower(l, status, True)
        self.speak_dialog("status.all", {"status": status})

    @intent_handler(IntentBuilder("").require("light").require("appearance").optionally("pattern").optionally("color").build())
    def changeAppearance(self, message):
        text = message.data.get("utterance").lower()
        pattern = message.data.get("pattern")
        color = self.getValidColor(message.data.get("color"))
        name = next((name for name in self.light_names if name in text), None)
        if not name:
            name = self.promptName()
        if not pattern:
            pattern = self.promptPattern()
        pattern = self.getValidPattern(pattern)
        colors = None
        if pattern in ["plain", "runner"]:
            if not color:
                colors = self.promptColors(1)
            else:
                colors = [color]
        if pattern == "gradient":
            colors = self.promptColors(2)
        timeout = None
        try:
            timeout = int(re.search(r"\d+", text).group(0))
        except:
            pass
        if pattern in ["runner", "fading", "rainbow"]:
            if not (timeout and int(timeout) > 1 and int(timeout) < 10000):
                if pattern in ["runner", "fading", "rainbow"]:
                    timeout = self.promptTimeout()
        self.lightPattern(name, pattern, colors=colors, timeout=timeout)

    def promptName(self):
        while True:
            newName = self.get_response("what.name")
            if newName in self.light_names:
                return newName
            elif newName in ["exit", "abbort"]:
                self.speak_dialog("abort")
                return None
            else:
                self.speak_dialog(
                    "invalid", {"value": newName, "var": "name"})

    def promptPattern(self):
        while True:
            pattern = self.get_response("what.pattern")
            if pattern in self.patterns:
                return pattern
            elif pattern in ["exit", "abbort"]:
                self.speak_dialog("abort")
                return None
            else:
                self.speak_dialog(
                    "invalid", {"value": pattern, "var": "pattern"})

    def promptColors(self, count):
        colors = []
        for i in range(count):
            if count > 1:
                self.speak_dialog("color.index", {"index": i+1})
            colorValid = False
            while not colorValid:
                color = self.get_response("what.color")
                color = color.replace(" ", "")
                if color in ["exit", "abort"]:
                    self.speak_dialog("abort")
                    return None
                c = None
                try:
                    c = Color(color)
                    colors.append(c.hex)
                    colorValid = True
                except:
                    self.speak_dialog(
                        "invalid", {"value": color, "var": "color"})
        return colors

    def promptTimeout(self):
        validTimeout = None
        timeoutValid = False
        while not timeoutValid:
            timeout = self.get_response("what.timeout")
            if timeout in ["exit", "abbort"]:
                self.speak_dialog("abort")
                return None
            try:
                validTimeout = int(timeout)
                timeoutValid = True
            except:
                self.speak_dialog(
                    "invalid", {"value": timeout, "var": "timeout"})
        return validTimeout

    def lightPower(self, name, status, quiet=False):
        light_id = [l["id"]
                    for l in self.lights if l["name"].lower() == name][0]
        r = requests.patch("http://devlight.local/lights/" +
                           light_id + "/" + status, headers=self.headers, data="{}")
        if not quiet:
            if r.status_code == 304:
                self.speak_dialog('status.304.name',
                                  {"name": name, "status": status})
            if r.status_code == 200:
                self.speak_dialog('status.name',
                                  {"name": name, "status": status})
            if r.status_code > 400:
                self.speak_dialog("error")

    def lightPattern(self, name, pattern, **kw):
        light_id = [l["id"]
                    for l in self.lights if l["name"].lower() == name][0]
        data = {"pattern": pattern,
                "colors": kw["colors"] if "colors" in kw else [], "timeout": kw["timeout"] if "timeout" in kw else None}
        r = requests.patch("http://devlight.local/lights/" + light_id +
                           "/color", headers=self.headers, data=json.dumps(data))
        self.write("log.json", json.dumps(r.json()))
        message = r.json()["message"]
        if (not "quiet" in kw) or not kw["quiet"] == True:
            if r.status_code == 304:
                self.speak_dialog('color.304.name',
                                  {"name": name})
            if r.status_code == 200:
                self.speak_dialog('color.name',
                                  {"name": name, "pattern": pattern})
            if r.status_code >= 400:
                if "off" in message.lower():
                    self.lightPower(name, "on", True)
                    self.lightPattern(name, pattern, timeout=kw["timeout"] if "timeout" in kw else None, colors=kw["colors"] if "colors" in kw else [
                    ], quiet=kw["quiet"] if "quiet" in kw else None)
                else:
                    self.speak_dialog(message if isinstance(
                        message, str) else message[0])

    def getValidColor(self, color):
        if not color:
            return None
        try:
            return Color(color).hex
        except:
            return None

    def getValidPattern(self, pattern):
        if pattern in ["plain", "single color"]:
            return "plain"
        if pattern in ["gradient", "two colors"]:
            return "gradient"
        if pattern in ["runner", "running"]:
            return "runner"
        if pattern in ["fading"]:
            return "fading"
        if pattern in ["party", "rainbow"]:
            return "rainbow"

    def write(self, file, message):
        with self.file_system.open(file, "w") as my_file:
            my_file.write(message)


def create_skill():
    return Devlight()
