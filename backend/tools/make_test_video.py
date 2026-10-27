"""Gera um vídeo de teste com fala sintética (espeak-ng) e um rosto que muda de lugar.

Também escreve <saida>.words.json com o tempo de cada palavra, para rodar o
pipeline com TRANSCRIBER=sidecar quando o modelo do Whisper não está disponível.

Uso: python tools/make_test_video.py saida.mp4
Requer: ffmpeg, espeak-ng, scikit-image (só pela foto de exemplo com rosto).
"""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import cv2
from skimage import data

RATE = 22050
SCRIPT = [
    ("Bom dia pessoal, sejam bem vindos a mais um vídeo do canal.", 0.6),
    ("Hoje eu quero falar sobre um assunto que parece chato, mas não é.", 0.5),
    ("Hum", 0.9),
    ("Vamos falar sobre organização financeira para quem está começando.", 1.4),
    ("Antes de tudo, deixa eu contar uma coisa rápida sobre a semana.", 0.5),
    ("Eu fui ao mercado, esqueci a lista, voltei para casa e fui de novo.", 0.6),
    ("Enfim, nada demais, só um dia comum.", 1.6),
    ("Você sabia que o maior erro de quem tenta guardar dinheiro é não anotar nada?", 0.4),
    ("Ninguém consegue melhorar o que não mede.", 0.4),
    ("Eu descobri isso do pior jeito, perdendo dez mil reais em um ano!", 0.5),
    ("O segredo é simples: anote cada gasto durante trinta dias.", 0.4),
    ("No fim do mês, você vai ver para onde o dinheiro está indo.", 0.4),
    ("E o resultado mudou a minha vida financeira completamente!", 0.5),
    ("Essa é a dica mais importante de todo o vídeo.", 1.5),
    ("Bom, agora deixa eu ajustar aqui a câmera.", 0.7),
    ("Hum", 1.2),
    ("Pronto, acho que agora está melhor, vamos continuar.", 1.8),
    ("Por que a maioria das pessoas nunca consegue sair das dívidas?", 0.5),
    ("Porque elas tentam pagar tudo ao mesmo tempo.", 0.4),
    ("O jeito certo é atacar primeiro a dívida com os juros mais altos.", 0.4),
    ("Cartão de crédito e cheque especial cobram mais de dez por cento ao mês!", 0.5),
    ("Imagina pagar isso durante um ano inteiro.", 0.4),
    ("Cuidado com essa armadilha, ela é a verdade que ninguém te conta.", 0.5),
    ("Quite essas primeiro e depois cuide do resto.", 1.6),
    ("Bom, era isso que eu tinha para hoje.", 0.5),
    ("Se gostou, deixa o seu comentário aqui embaixo.", 0.5),
    ("Até o próximo vídeo, tchau tchau.", 1.0),
]
# posição X do rosto no quadro 1920x1080 ao longo do tempo (segundos)
FACE_POSITIONS = [(0, 260), (45, 1150), (95, 700)]


def tts(text: str, path: Path, speed: int) -> None:
    subprocess.run(["espeak-ng", "-v", "pt-br", "-s", str(speed), "-w", str(path), text],
                   check=True)


def main(out: Path) -> None:
    tmp = Path(tempfile.mkdtemp())
    pcm, words, t = bytearray(), [], 0.5
    pcm += b"\x00\x00" * int(RATE * 0.5)

    for i, (sentence, pause) in enumerate(SCRIPT):
        wav = tmp / f"s{i}.wav"
        tts(sentence, wav, speed=160 + (i % 3) * 15)
        with wave.open(str(wav)) as w:
            assert w.getframerate() == RATE, w.getframerate()
            frames = w.readframes(w.getnframes())
        # espeak põe ~silêncio no fim; descartamos o que estiver abaixo do limiar
        samples = memoryview(frames).cast("h")
        last = max((k for k in range(len(samples)) if abs(samples[k]) > 300), default=0)
        frames = frames[: (last + 1) * 2]
        dur = len(frames) / 2 / RATE

        # tempo por palavra proporcional ao número de letras (aproximação)
        tokens = sentence.split()
        weights = [len(tok.strip(".,!?:")) + 2 for tok in tokens]
        acc = t
        for tok, wgt in zip(tokens, weights):
            wd = dur * wgt / sum(weights)
            words.append({"word": tok, "start": round(acc + 0.02, 3),
                          "end": round(acc + wd - 0.02, 3), "prob": 1.0})
            acc += wd
        pcm += frames + b"\x00\x00" * int(RATE * pause)
        t += dur + pause

    audio = tmp / "audio.wav"
    with wave.open(str(audio), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(pcm))
    total = t + 0.5

    face = tmp / "face.png"
    cv2.imwrite(str(face), cv2.resize(data.astronaut()[:, :, ::-1], (560, 560)))
    x_expr = "0"
    for start, x in FACE_POSITIONS:
        x_expr = f"if(gte(t,{start}),{x},{x_expr})"
    vf = (f"[0:v][1:v]overlay=x='{x_expr}':y=260,"
          "drawtext=text='%{pts\\:hms}':x=40:y=40:fontsize=48:fontcolor=white:box=1:boxcolor=black@0.5"
          "[v]")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"gradients=s=1920x1080:c0=0x203a5a:c1=0x6a3a7a:speed=0.01:d={total:.2f}:r=30",
        "-loop", "1", "-i", str(face),
        "-i", str(audio),
        "-filter_complex", vf, "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)], check=True)
    out.with_suffix(".words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1))
    print(f"{out}: {total:.1f}s, {len(words)} palavras")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "test.mp4"))
