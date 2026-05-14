# Tutorial: Configuração de Inicialização Automática do Backend

Este guia explica como configurar o seu servidor Python (FastAPI) para iniciar automaticamente sempre que o Windows ligar.

## 1. O Script de Inicialização
Já criamos o arquivo `iniciar_backend.bat` nesta mesma pasta. Ele contém os comandos necessários para subir o servidor.

## 2. Configurando o Windows (Agendador de Tarefas)

Siga exatamente estes passos:

1.  **Abrir o Agendador**:
    *   Pressione a tecla `Windows` e digite **Agendador de Tarefas**. Abra-o.
2.  **Criar Tarefa**:
    *   No painel direito, clique em **Criar Tarefa Básica...**.
3.  **Identificação**:
    *   Nome: `Start Backend ITPS`
    *   Clique em **Avançar**.
4.  **Disparador**:
    *   Selecione **Ao iniciar o computador**.
    *   Clique em **Avançar**.
5.  **Ação**:
    *   Selecione **Iniciar um programa**.
    *   Clique em **Avançar**.
6.  **Caminho do Script**:
    *   Em "Programa/script", clique em **Procurar**.
    *   > [!IMPORTANT]
    *   > Vá até a pasta onde seu projeto está salvo (Exemplo: `C:\Users\gnsilva\BACKEND-ITPS-SITE\`) e selecione o arquivo `iniciar_backend.bat`. Se você mudou a pasta de lugar, certifique-se de selecionar o caminho novo!
    *   Clique em **Avançar**.
7.  **Finalizar**:
    *   Marque a caixa **Abrir a caixa de diálogo Propriedades desta tarefa ao clicar em Concluir**.
    *   Clique em **Concluir**.

## 3. Configurações de Segurança (ESSENCIAL)

Na janela que se abriu (Propriedades):

1.  Na aba **Geral**, procure por "Opções de segurança".
2.  Marque a opção **Executar quer o usuário esteja conectado ou não**. (Isso faz o backend ligar mesmo que o servidor esteja na tela de login).
3.  Marque a opção **Executar com privilégios mais altos**.
4.  Clique em **OK**.
5.  O Windows pedirá sua **senha de usuário**. Digite-a e confirme.

---

## Como testar?
Não precisa reiniciar o PC para testar. No Agendador de Tarefas:
1.  Clique em **Biblioteca do Agendador** à esquerda.
2.  Encontre sua tarefa `Start Backend ITPS` na lista central.
3.  Clique com o botão direito nela e selecione **Executar**.

Se o servidor FastAPI subir, a configuração está correta!
