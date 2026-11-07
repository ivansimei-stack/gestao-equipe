# Instalação no Windows

Leva uns 10 minutos e é feita **uma única vez**. O sistema roda só no seu computador:
ninguém mais tem acesso, e funciona sem internet depois de instalado.

## 1. Instalar o Python (se ainda não tiver)

1. Acesse **https://www.python.org/downloads/** e clique no botão amarelo **Download Python 3.x**.
2. Abra o arquivo baixado.
3. ⚠️ Na primeira tela, **marque a caixa “Add python.exe to PATH”** (fica embaixo).
4. Clique em **Install Now** e aguarde terminar.

> Computador da empresa pedindo senha de administrador? Peça à TI para instalar o
> Python 3 (versão 3.11 ou mais nova) com a opção “Add to PATH”.

## 2. Baixar o sistema

1. Acesse **https://github.com/ivansimei-stack/gestao-equipe** (entre com sua conta do GitHub).
2. Clique no botão verde **Code** → **Download ZIP**.
3. Na pasta Downloads, clique com o botão direito no ZIP → **Extrair tudo…**
4. Mova a pasta extraída para **Documentos** e renomeie para `gestao-equipe`
   (fica `Documentos\gestao-equipe`).

## 3. Instalar

1. Abra a pasta `gestao-equipe` e dê **dois cliques em `instalar.bat`**.
2. Se aparecer “O Windows protegeu o computador”, clique em **Mais informações → Executar assim mesmo**
   (aparece porque o arquivo veio da internet).
3. Aguarde as mensagens `[ok]` e a palavra **Pronto!**. Pressione qualquer tecla para fechar.

Foram criados dois atalhos na Área de Trabalho:

| Atalho | Para quê |
|---|---|
| **Gestão da Equipe** | O sistema de verdade, com os seus dados |
| **Gestão da Equipe (demonstração)** | Uma equipe fictícia para conhecer as telas. Não mexe nos seus dados e é recriada sempre que é aberta |

## 4. Usar no dia a dia

1. Dois cliques em **Gestão da Equipe** na Área de Trabalho.
2. Abre uma janela preta (é o sistema ligado) e, em seguida, o navegador no painel.
3. **Não feche a janela preta enquanto estiver usando.** Quando terminar, é só fechá-la.

Dica: no navegador, salve `http://127.0.0.1:8000` nos favoritos.

## Onde ficam os seus dados

Em **OneDrive\GestaoEquipe\gestao.db** (ou `Documentos\GestaoEquipe`, se não houver OneDrive).
Por estar no OneDrive, há **backup automático** e o histórico de versões do próprio OneDrive.
Para levar para outro computador, basta instalar lá também: ele usará o mesmo arquivo.

> Evite deixar o sistema aberto em **dois computadores ao mesmo tempo**: o OneDrive pode criar
> uma cópia em conflito do arquivo.

## Atualizar para uma versão nova

1. Baixe o ZIP novo (passo 2) e extraia.
2. Copie o conteúdo para dentro da pasta `Documentos\gestao-equipe`, **substituindo** os arquivos.
3. Rode o `instalar.bat` de novo. Seus dados e configurações são mantidos.

## Problemas comuns

| Sintoma | Solução |
|---|---|
| “Python não encontrado” | Reinstale o Python marcando **Add python.exe to PATH** |
| Erro ao “Instalar componentes” | A rede da empresa pode bloquear downloads (proxy). Tente em outra rede ou peça liberação de `pypi.org` à TI |
| A janela preta fecha sozinha com erro | Outra cópia já está aberta, ou a porta 8000 está em uso. Reinicie o computador e tente de novo |
| Página não abre | Confira se a janela preta está aberta e acesse `http://127.0.0.1:8000` |
