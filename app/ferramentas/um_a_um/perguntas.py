"""Banco de perguntas sugeridas para 1:1s."""
import random

PERGUNTAS = {
    "Bem-estar": [
        "Como você está, de verdade, nesta semana?",
        "O que tem drenado sua energia ultimamente?",
        "Como está o equilíbrio entre trabalho e vida pessoal?",
        "Tem algo fora do trabalho que esteja pesando e que eu deva saber?",
    ],
    "Trabalho atual": [
        "Qual foi sua maior conquista desde a última conversa?",
        "Onde você está travado(a) e como posso ajudar?",
        "Tem alguma prioridade que não está clara para você?",
        "Se pudesse mudar uma coisa no nosso processo, o que seria?",
    ],
    "Carreira e crescimento": [
        "O que você quer aprender nos próximos meses?",
        "Que tipo de projeto te deixaria mais motivado(a)?",
        "Onde você se vê daqui a 2 anos? O que falta para chegar lá?",
        "Que habilidade você gostaria de desenvolver com meu apoio?",
    ],
    "Equipe": [
        "Como está a colaboração com o restante do time?",
        "Tem alguém da equipe que merece um reconhecimento?",
        "Existe algum conflito ou ruído que eu deveria saber?",
    ],
    "Feedback para a gestão": [
        "O que eu poderia fazer diferente para te apoiar melhor?",
        "Tem alguma decisão recente que você não entendeu ou discorda?",
        "Você está recebendo feedback suficiente de mim?",
    ],
}


def sugestoes(n: int = 3, semente: int | None = None) -> list[tuple[str, str]]:
    rnd = random.Random(semente)
    categorias = rnd.sample(list(PERGUNTAS), k=min(n, len(PERGUNTAS)))
    return [(c, rnd.choice(PERGUNTAS[c])) for c in categorias]
