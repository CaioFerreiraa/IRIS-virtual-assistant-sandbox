from multiprocessing import freeze_support
from RealtimeSTT import AudioToTextRecorder


def main():
    print("Inicializando...")

    recorder = AudioToTextRecorder(language="pt", model="large-v2")

    print("Pode falar!")

    while True:
        texto = recorder.text()

        if texto:
            print("Você disse:", texto)


if __name__ == "__main__":
    freeze_support()
    main()