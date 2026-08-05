import queue
import sys
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

def main():
    print("Inicializando modelo...")
    
    # --- CONFIGURAÇÕES ---
    MODELO = "medium"
    IDIOMA = "pt"
    SAMPLE_RATE = 16000  # Taxa de amostragem padrão do Whisper
    
    # SEGREDO PARA OS NOMES: Adicione aqui os nomes que você quer que ele acerte
    PROMPT_NOMES = "Nome de pessoa: Íris, Iris. A Íris falou que vai participar."
    
    # Se você tiver GPU NVIDIA: device="cuda", compute_type="float16"
    # Se for rodar APENAS na CPU: device="cpu", compute_type="int8" (muito leve)
    model = WhisperModel(MODELO, device="cpu", compute_type="int8")
    
    # Configurações de detecção de fala (Ajuste se o seu quarto tiver muito ruído)
    THRESHOLD = 0.025      # Volume mínimo para considerar que você está falando
    SILENCE_LIMIT = 1.2   # Segundos de silêncio para entender que você terminou a frase
    # ---------------------

    audio_queue = queue.Queue()

    def callback(indata, frames, time, status):
        """Esta função é chamada automaticamente a cada bloco de áudio do microfone"""
        if status:
            print(status, file=sys.stderr)
        audio_queue.put(indata.copy())

    print("Pode falar!")

    audio_buffer = []
    silence_duration = 0
    falando = False

    # Abre o fluxo do microfone de forma eficiente
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback, dtype="float32"):
        while True:
            # Pega o bloco de áudio capturado
            data = audio_queue.get()
            audio_buffer.append(data)
            
            # Calcula o volume (RMS) do bloco atual
            volume = np.sqrt(np.mean(data**2))
            
            if volume > THRESHOLD:
                falando = True
                silence_duration = 0
            else:
                if falando:
                    silence_duration += len(data) / SAMPLE_RATE
            
            # Se o usuário estava falando e parou pelo tempo limite, processa o áudio
            if falando and silence_duration >= SILENCE_LIMIT:
                # Junta todo o áudio gravado em um único vetor
                audio_completo = np.concatenate(audio_buffer, axis=0).flatten()
                
                # Reseta o buffer para a próxima frase
                audio_buffer = []
                falando = False
                silence_duration = 0
                
                # Transcrição rápida usando o faster-whisper
                segments, info = model.transcribe(
                    audio_completo, 
                    language=IDIOMA, 
                    initial_prompt=PROMPT_NOMES, # Força o reconhecimento dos nomes
                    vad_filter=True              # VAD interno para remover ruídos de fundo
                )
                
                # Junta o texto de todos os segmentos gerados
                texto = "".join([segment.text for segment in segments]).strip()
                
                if texto:
                    print("Você disse:", texto)


if __name__ == "__main__":
    # O faster-whisper gerencia threads nativamente em C++, 
    # não precisa obrigatoriamente do freeze_support, mas mantemos por segurança.
    main()