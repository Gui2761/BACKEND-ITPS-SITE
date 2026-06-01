# 🐳 Guia de Inicialização e Execução do Backend (Docker & Linux)

Este guia explica como gerenciar e configurar a inicialização automática do servidor backend Python (FastAPI) em um ambiente **Linux** utilizando **Docker** e **Docker Compose**.

---

## 🚀 1. Executando com Docker Compose

O backend é executado dentro de um container Docker, facilitando a portabilidade e isolando as dependências.

### Comandos Principais:

*   **Iniciar os serviços em segundo plano (background):**
    ```bash
    docker compose up -d
    ```
*   **Parar os serviços:**
    ```bash
    docker compose down
    ```
*   **Visualizar os logs em tempo real:**
    ```bash
    docker compose logs -f
    ```
*   **Reconstruir a imagem (após alterações no código ou dependencies):**
    ```bash
    docker compose up -d --build
    ```

---

## 🔄 2. Configurando a Inicialização Automática (Boot do Linux)

Para garantir que o backend suba automaticamente sempre que o servidor Linux for ligado/reiniciado, siga as etapas abaixo:

### Passo 2.1 — Configurar Inicialização Automática do Docker Daemon
Garanta que o próprio serviço do Docker inicie com o sistema operacional:
```bash
sudo systemctl enable docker
sudo systemctl start docker
```

### Passo 2.2 — Política de Reinicialização dos Containers
No arquivo `docker-compose.yml`, a linha `restart: unless-stopped` já está configurada. Isso faz com que o Docker reinicie o container automaticamente em caso de falhas ou reinicialização do sistema operacional, a menos que ele tenha sido parado manualmente (`docker compose down`).

---

## 📂 3. Montagem dos Volumes de Rede (SMB/CIFS)

Como o backend precisa ler bancos de dados Access/arquivos das pastas de rede (`172.23.6.7`), no Linux essas pastas precisam ser montadas via protocolo **CIFS** no sistema de arquivos antes de serem mapeadas no Docker.

### Exemplo de Configuração de Montagem no `/etc/fstab` do Linux:

Para persistir a montagem das pastas de rede no boot do Linux:

1. Instale o suporte a CIFS no servidor Linux:
   ```bash
   sudo apt-get install cifs-utils  # Debian/Ubuntu
   # ou
   sudo yum install cifs-utils      # RHEL/CentOS
   ```

2. Crie os pontos de montagem locais:
   ```bash
   sudo mkdir -p /mnt/db_contratos
   sudo mkdir -p /mnt/db_folha
   ```

3. Adicione as seguintes linhas no final do arquivo `/etc/fstab`:
   ```text
   //172.23.6.7/ageplan/Banco de contratos /mnt/db_contratos cifs guest,uid=1000,gid=1000,iocharset=utf8 0 0
   //172.23.6.7/gerh/1- COAPE/FolhaITPS_Dados /mnt/db_folha cifs guest,uid=1000,gid=1000,iocharset=utf8 0 0
   ```
   *(Nota: Substitua `guest` pelas credenciais de rede apropriadas, caso o compartilhamento exija usuário e senha: `username=seu_usuario,password=sua_senha`)*.

4. Atualize o `docker-compose.yml` para apontar os volumes locais para essas pastas montadas no Linux:
   ```yaml
   volumes:
     - "/mnt/db_contratos:/app/db_contratos"
     - "/mnt/db_folha:/app/db_folha"
   ```

---

## 🔍 Como verificar se está funcionando?

1. Verifique se os caminhos locais estão montados e acessíveis:
   ```bash
   ls -la /mnt/db_contratos
   ```
2. Verifique se o container está rodando e respondendo na porta `8000`:
   ```bash
   docker ps
   curl http://localhost:8000/api/pca/health  # Ou qualquer endpoint de validação
   ```
