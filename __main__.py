# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

import sys

from threading import Thread, Lock, Event

from os.path import exists
from mycroft.stt import STTFactory
from mycroft.configuration import Configuration
from mycroft.util.log import LOG
from mycroft.messagebus.client import MessageBusClient
from mycroft.messagebus.message import Message
import speech_recognition as sr
import time
from os import remove

authors = ["aix", "forslund", "jarbas"]

bus = None

config = Configuration.get()

def connect(bus):
    bus.run_forever()

def read_wave_file(wave_file_path):
    '''
    reads the wave file at provided path and return the expected
    Audio format
    '''
    # use the audio file as the audio source
    r = sr.Recognizer()
    with sr.AudioFile(wave_file_path) as source:
        audio = r.record(source)
    return audio

class FileConsumer(Thread):
    def __init__(self, file_location='/tmp/mycroft_in.wav', emitter=None):
        super(FileConsumer, self).__init__()
        self.path = file_location
        self.stop_event = Event()
        self.stt = None
        self.emitter = emitter

    def run(self):
        LOG.info("Creating SST interface")
        self.stt = STTFactory.create()
        self.emitter.on("stt.request", self.handle_external_request)
        LOG.info("Stt Creation P2")
        while not self.stop_event.is_set():
            if exists(self.path):
                audio = read_wave_file(self.path)
                text = self.stt.execute(audio).lower().strip()
                LOG.info(text)
                self.emitter.emit(
                    Message("recognizer_loop:utterance", 
                           {"utterances": [text]},
                           {"source": "wav_client"}))
                remove(self.path)
            time.sleep(0.5)

    def handle_external_request(self, message):
        file = message.data.get("File")
        if self.stt is None:
            error = "STT initialization failure"
            LOG.info(error)
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        elif not file:
            error = "No file provided for transcription"
            LOG.info(error)
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        elif not exists(file):
            error = "Invalid file path provided for transcription"
            LOG.info(error)
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        else:
            audio = read_wave_file(file)
            transcript = self.stt.execute(audio).lower().strip()
            self.emitter.emit(Message("stt.reply",
                                      {"transcription": transcript}))

    def stop(self):
        self.stop_event.set()


def main():
    global bus
    global config
    bus = MessageBusClient()
    event_thread = Thread(target=connect, args=[bus])
    event_thread.setDaemon(True)
    event_thread.start()
    config = config.get("wav_client", {"path": "/tmp/mycroft_in.wav"})
    try:
        file_consumer = FileConsumer(file_location=config["path"], emitter=bus)
        file_consumer.start()
        while True:
            time.sleep(1000)
    except KeyboardInterrupt as e:
        LOG.exception(e)
        LOG.info("Here in E")
        file_consumer.stop()
        file_consumer.join()
        sys.exit()


if __name__ == "__main__":
    main()
