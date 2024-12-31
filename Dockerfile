FROM python:3.12
LABEL authors="julioNolasco"

# Instalar iproute2 (para manipulcao de rotas)
RUN apt-get update && apt-get install -y iproute2
RUN apt-get update && apt-get install -y iputils-ping

# Copie o arquivo known_hosts para o contêiner
COPY ~/.ssh/known_hosts /root/.ssh/known_hosts

# Configure permissões adequadas para o arquivo
RUN chmod 700 /root/.ssh && \
    chmod 644 /root/.ssh/known_hosts

WORKDIR /app

# Copia o arquivo de requisitos do projeto
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do projeto para o contêiner
COPY . .

# Expõe a porta padrão do Django
EXPOSE 8000

# Comando padrão para iniciar o servidor de desenvolvimento do Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]