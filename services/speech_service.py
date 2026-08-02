class SpeechService:
    def listen(self) -> str:
        raise NotImplementedError("Speech input ainda nao foi implementado.")

    def speak(self, text: str) -> None:
        raise NotImplementedError("Speech output ainda nao foi implementado.")
