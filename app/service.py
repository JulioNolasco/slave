import os
import time
from datetime import datetime, timedelta
import requests
import environ
import json
from pathlib import Path
import paramiko
import telnetlib
import logging
from requests.exceptions import RequestException
from django.http import HttpResponse
import threading
import requests
import environ


# Carrega as variáveis de ambiente do arquivo .env
env = environ.Env()
environ.Env.read_env()  # Carrega o arquivo .env

# Configurações da API
API_URL = env('API_URL')
TOKEN = env('TOKEN_USUARIO')
HEADERS = {"Authorization": f"Token {TOKEN}"}

# Pasta de backups
BASE_DIR = Path(__file__).resolve().parent
PASTA_BACKUP = Path("/app/backups")  # Defina a pasta corretamente
os.makedirs(PASTA_BACKUP, exist_ok=True)


# Função para verificar se o backup já foi feito hoje
def backup_hoje_realizado():
    """Verifica se o backup já foi feito hoje, armazenando a data do último backup em um arquivo"""
    data_hoje = datetime.now().date()
    arquivo_backup = "ultimo_backup.txt"

    if os.path.exists(arquivo_backup):
        with open(arquivo_backup, 'r') as f:
            data_ultimo_backup = f.read().strip()
            if data_ultimo_backup == str(data_hoje):
                return True
    return False


# Atualiza o controle local
def atualizar_data_ultimo_backup():
    """
    Atualiza a data do último backup realizado localmente no arquivo.
    """
    data_hoje = datetime.now().date()
    with open("ultimo_backup.txt", 'w') as f:
        f.write(str(data_hoje))
    print(f"Data do último backup atualizada localmente para: {data_hoje}")


# Salva o backup no diretório local
def salvar_backup(nome_equipamento, conteudo_backup):
    pasta_equipamento = PASTA_BACKUP / nome_equipamento
    pasta_equipamento.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho_arquivo = pasta_equipamento / f"{nome_equipamento}_{timestamp}.txt"

    try:
        if not conteudo_backup:
            print(f"Erro: conteúdo do backup está vazio para {nome_equipamento}.")
            return None

        # Salvar o conteúdo no arquivo
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo_backup)
        print(f"Backup salvo em: {caminho_arquivo}")

    except Exception as e:
        print(f"Erro ao salvar o backup no caminho {caminho_arquivo}: {e}")
        return None

    return caminho_arquivo


# Envia o arquivo de backup via API
def enviar_arquivo_api(nome_equipamento, caminho_arquivo):
    """
    Envia o arquivo de backup para o servidor principal via API HTTP.
    """
    # Substitui o equipamento_id pelo nome do equipamento na URL
    url = f"{API_URL}/backups/{nome_equipamento}/"  # Nome do equipamento na URL

    with open(caminho_arquivo, 'rb') as f:
        files = {'file': f}  # Arquivo a ser enviado

        try:
            response = requests.post(url, headers=HEADERS, files=files)
            response.raise_for_status()  # Verifica se a resposta foi 2xx
            if response.status_code == 201:
                print(f"Backup enviado com sucesso para {nome_equipamento}: {caminho_arquivo}")
            else:
                print(f"Erro ao enviar backup via API: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao enviar o arquivo via API: {e}")


def enviar_arquivo_ftp(caminho_arquivo, nome_equipamento):
    """
    Envia o arquivo de backup via FTP para o servidor.
    """
    servidor_ftp = "177.52.216.4"  # IP do servidor FTP
    usuario_ftp = "backup"
    senha_ftp = "Anas2108@@"
    pasta_destino = f"/{nome_equipamento}/"  # Caminho correto no servidor FTP
    porta_ftp = 21  # Porta do FTP

    from ftplib import FTP

    print(f"Conectando ao servidor FTP: {servidor_ftp}")
    try:
        # Criando uma instância do cliente FTP
        ftp = FTP()
        ftp.connect(servidor_ftp, porta_ftp)
        ftp.login(usuario_ftp, senha_ftp)

        print(f"Conectado ao FTP. Verificando diretório: {pasta_destino}")
        # Verifica se o diretório existe e cria se necessário
        try:
            ftp.cwd(pasta_destino)
        except Exception:
            print(f"Diretório {pasta_destino} não existe. Criando...")
            ftp.mkd(pasta_destino)
            ftp.cwd(pasta_destino)

        # Envia o arquivo
        with open(caminho_arquivo, "rb") as f:
            nome_arquivo = os.path.basename(caminho_arquivo)
            print(f"Enviando arquivo {nome_arquivo} para o FTP...")
            ftp.storbinary(f"STOR {nome_arquivo}", f)

        print(f"Arquivo {nome_arquivo} enviado com sucesso para {pasta_destino}")
        ftp.quit()

    except Exception as e:
        print(f"Erro ao enviar o arquivo via FTP: {e}")


# Atualiza o campo 'ultimo_backup' via API no servidor master
def atualizar_ultimo_backup(equipamento_id):

    url = f"{API_URL}/equipments/{equipamento_id}/update_backup/"
    print(f"URL gerada para atualização: {url}")  # Depuração
    data_atual = datetime.now().isoformat()
    payload = {"ultimo_backup": data_atual}


    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
        print(f"Resposta do servidor: {response.status_code} - {response.text}")
        if response.status_code == 200:
            print(f"Último backup atualizado com sucesso para o equipamento {equipamento_id}. Data enviada: {data_atual}")
        else:
            print(f"Erro ao atualizar último backup: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar atualização do último backup: {e}")


# Atualiza o campo 'ultima_comunicacao' via API no servidor master
def atualizar_ultima_comunicacao():
    """
    Atualiza a última comunicação da empresa no servidor master via API.
    """
    url = f"{API_URL}/enterprises/update_comunicacao/"
    print(f"URL gerada para atualização: {url}")  # Depuração
    data_atual = datetime.now().isoformat()
    payload = {"ultima_comunicacao": data_atual}

    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
        print(f"Resposta do servidor: {response.status_code} - {response.text}")
        if response.status_code == 200:
            print(f"Última comunicação atualizada com sucesso. Data enviada: {data_atual}")
        else:
            print(f"Erro ao atualizar última comunicação: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao enviar atualização da última comunicação: {e}")


def limpar_resposta(resposta, comando):
    """
    Limpa a resposta para remover o comando inicial e o prompt final.
    """
    linhas = resposta.splitlines()

    # Remove o comando inicial
    if linhas and comando in linhas[0]:
        linhas.pop(0)

    # Remove o prompt final
    if linhas and linhas[-1].strip().endswith("#"):
        linhas.pop(-1)

    # Junta as linhas restantes
    return "\n".join(linhas)


def realizar_backup(equipamento):
    print(f"Iniciando backup para {equipamento['descricao']} ({equipamento['ip']})")

    comando_backup = equipamento['ScriptEquipment']['Script']
    protocolo = equipamento['access_type'].upper()

    try:
        # Escolhe a função correta (SSH ou Telnet) com base no protocolo
        if protocolo == "SSH":
            resposta = acessar_ssh(
                id=equipamento['id'],
                ip=equipamento['ip'],
                usuario=equipamento['usuarioacesso'],
                senha=equipamento['senhaacesso'],
                porta=equipamento['portaacesso'],
                comando=comando_backup,
                nome_equipamento=equipamento['descricao']
            )
        elif protocolo == "TELNET":
            resposta = acessar_telnet(
                id=equipamento['id'],
                ip=equipamento['ip'],
                usuario=equipamento['usuarioacesso'],
                senha=equipamento['senhaacesso'],
                porta=equipamento['portaacesso'],
                comando=comando_backup,
                nome_equipamento=equipamento['descricao']
            )
        else:
            print(f"Protocolo inválido: {protocolo}")
            return

        # Limpar a resposta
        resposta_limpa = limpar_resposta(resposta, comando_backup)
        print(f"Resposta limpa capturada:\n{resposta_limpa}")

        # Salvar backup apenas se a resposta limpa não estiver vazia
        if resposta_limpa:
            caminho_arquivo = salvar_backup(equipamento['descricao'], resposta_limpa)
        else:
            print(f"Resposta para {equipamento['descricao']} está vazia após limpeza. Backup não salvo.")


        caminho_arquivo = salvar_backup(equipamento['descricao'], resposta_limpa)

        if caminho_arquivo is None:
            print("Erro: Caminho do arquivo retornado é None. Abortando envio para o FTP.")
            return

        enviar_arquivo_ftp(caminho_arquivo, equipamento['descricao'])

        # Atualiza a data do último backup via API
        try:
            atualizar_ultimo_backup(equipamento['id'])
        except Exception as e:
            print(f"Erro ao atualizar o último backup no servidor primário: {e}")

        # Atualiza o controle local de backup
        try:
            atualizar_data_ultimo_backup()
        except Exception as e:
            print(f"Erro ao atualizar o controle local de backup: {e}")

    except Exception as e:
        print(f"Erro ao realizar backup: {e}")


# Função para executar backups de todos os equipamentos
def executar_backups():
    json = {
        "backup": "Sim"
    }
    response = requests.get(f'{API_URL}/equipments', headers=HEADERS, params=json)

    if response.status_code == 200:
        equipamentos = response.json()

        if not equipamentos:
            print("Nenhum equipamento ativo para backup.")
            return

        # Filtra os equipamentos que possuem o campo "backup" igual a "Sim"
        equipamentos_para_backup = [equipamento for equipamento in equipamentos if equipamento.get('backup') == 'Sim']

        if not equipamentos_para_backup:
            print("Nenhum equipamento com backup marcado como 'Sim'.")
            return

        for equipamento in equipamentos_para_backup:
            realizar_backup(equipamento)


    else:
        print(f"Erro ao buscar equipamentos: {response.status_code}")


"""
Acessa o equipamento via SSH e executa comandos.
"""
def acessar_ssh(id, ip, usuario, senha, porta, comando, nome_equipamento, tempo_maximo=60):
    # Obtenha a chave pública do servidor
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Política de adicionar automaticamente

    # Configuração básica para logs
    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')


    try:
        cliente.connect(ip, port=porta, username=usuario, password=senha, timeout=30)

        # Criação do canal
        canal = cliente.invoke_shell()
        canal.settimeout(2)

        # Captura da mensagem inicial
        print("Capturando mensagem inicial via SSH...")
        capturar_prompt(canal, [">", "#"], 30)

        # Desativar paginação
        print("Desativando paginação via SSH...")
        #canal.send("terminal length 0\n")
        time.sleep(2)

        # Aguardando estabilização
        print("Aguardando equipamento estabilizar...")
        time.sleep(2)

        # Envia o comando principal
        print(f"Executando comando via SSH no equipamento {nome_equipamento}...")
        canal.send(comando + '\n')

        # Captura da resposta
        resposta = capturar_resposta(canal, [">", "#"], tempo_maximo)
        return resposta

    except paramiko.ssh_exception.SSHException as e:
        # Este bloco captura erros relacionados ao SSH, incluindo problemas de chave
        print(f"Erro SSH: {str(e)}")
        raise Exception(f"Erro ao acessar o equipamento via SSH: {str(e)}")

    except Exception as e:
        # Captura qualquer outro erro genérico
        print(f"Erro geral: {str(e)}")
        raise Exception(f"Erro geral ao acessar o equipamento via SSH: {str(e)}")

    finally:

        cliente.close()


"""
Acessa o equipamento via TELNET e executa comandos.
"""
def acessar_telnet(id, ip, usuario, senha, porta, comando, nome_equipamento, tempo_maximo=60):
    """
    Acessa o equipamento via Telnet e executa comandos.
    """
    try:
        print(f"Conectando via Telnet ao equipamento {nome_equipamento}...")
        cliente = telnetlib.Telnet(ip, port=porta, timeout=30)

        # Envia credenciais
        cliente.read_until(b"login: ", timeout=10)
        cliente.write(usuario.encode('ascii') + b"\n")
        cliente.read_until(b"Password: ", timeout=10)
        cliente.write(senha.encode('ascii') + b"\n")

        # Captura da mensagem inicial
        print("Capturando mensagem inicial via Telnet...")
        capturar_prompt(cliente, ">#", tempo_maximo)

        # Desativando paginação
        print("Desativando paginação via Telnet...")
        cliente.write(b"terminal length 0\n")
        time.sleep(2)
        cliente.read_very_eager()  # Limpa o buffer

        # Aguardando estabilização
        print("Aguardando equipamento estabilizar...")
        time.sleep(2)

        # Envia o comando principal
        print(f"Executando comando via Telnet no equipamento {nome_equipamento}...")
        cliente.write(comando.encode('ascii') + b"\n")

        # Captura da resposta
        resposta = capturar_resposta(cliente, [">", "#"], tempo_maximo)
        return resposta

    except Exception as e:
        raise Exception(f"Erro ao acessar o equipamento via Telnet: {str(e)}")


# Função para capturar o prompt inicial
def capturar_prompt(conexao, prompts, tempo_maximo):
    """
    Captura o prompt inicial até encontrar um dos prompts esperados ou estourar o tempo.
    """
    inicio = time.time()
    while True:
        if isinstance(conexao, paramiko.Channel) and conexao.recv_ready():
            mensagem_inicial = conexao.recv(4096).decode('utf-8')
            if any(mensagem_inicial.strip().endswith(p) for p in prompts):
                print("Prompt inicial capturado via SSH.")
                break
        elif isinstance(conexao, telnetlib.Telnet):
            mensagem_inicial = conexao.read_very_eager().decode('ascii')
            if any(mensagem_inicial.strip().endswith(p) for p in prompts):
                print("Prompt inicial capturado via Telnet.")
                break

        if time.time() - inicio > tempo_maximo:
            raise Exception("Tempo limite ao capturar a mensagem inicial.")
        time.sleep(1)


def capturar_resposta(conexao, prompts, tempo_maximo):
    """
    Captura a resposta do comando até encontrar um dos prompts esperados ou estourar o tempo.
    Lida corretamente com paginação (--More--) e continua executando o comando.
    """
    resposta = ""
    inicio = time.time()

    while True:
        if isinstance(conexao, paramiko.Channel) and conexao.recv_ready():
            resposta_parcial = conexao.recv(4096).decode('utf-8')

            # Lida com paginação e envia espaço para continuar
            if "--More--" or "more" in resposta_parcial:
                conexao.send(" ")  # Envia espaço para continuar
                resposta_parcial = resposta_parcial.replace("--More--", "")  # Remove '--More--'

            resposta += resposta_parcial
            print(f"Resposta parcial capturada via SSH:\n{resposta_parcial}")

            # Verifica se chegou ao fim do comando
            if any(resposta.strip().endswith(p) for p in prompts):
                print("Comando concluído via SSH.")
                break

        elif isinstance(conexao, telnetlib.Telnet):
            resposta_parcial = conexao.read_very_eager().decode('ascii')

            # Lida com paginação e envia espaço para continuar
            if "--More--" or "more" in resposta_parcial:
                print("Detectado '--More--', enviando espaço via Telnet...")
                conexao.write(b" ")  # Envia espaço para continuar
                resposta_parcial = resposta_parcial.replace("--More--", "")  # Remove '--More--'

            resposta += resposta_parcial
            print(f"Resposta parcial capturada via Telnet:\n{resposta_parcial}")

            # Verifica se chegou ao fim do comando
            if any(resposta.strip().endswith(p) for p in prompts):
                print("Comando concluído via Telnet.")
                break

        # Verifica tempo limite
        if time.time() - inicio > tempo_maximo:
            raise Exception("Tempo limite excedido ao aguardar resposta do equipamento.")
        time.sleep(0.5)  # Reduzido para capturar dados com mais frequência

    return resposta


# Envia o backup via FTP
def enviar_backup(equipamento_id, caminho_arquivo, nome_equipamento):
    try:
        # Envia via FTP para o diretório correto
        enviar_arquivo_ftp(caminho_arquivo, nome_equipamento)

    except Exception as e:
        print(f"Erro no envio via FTP: {e}")


# Obtém o horário agendado e o tempo de backup via API
def obter_horario_backup():
    url = f"{API_URL}/enterprises"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        empresas = response.json()
        if empresas and isinstance(empresas, list):
            horario_backup = empresas[0].get("horario_backup")
            tempo_backup = empresas[0].get("tempo_backup")
            print(f"Horário agendado para: {horario_backup} e tempo em segundo de um backup para o outro: {tempo_backup}")
            return horario_backup, tempo_backup
    print(f"Erro ao obter dados da API: {response.status_code}")
    return None, None


# Função para rodar o backup em segundo plano
def processar_backups_background():
    horario_agendado, tempo_backup = obter_horario_backup()
    if not horario_agendado or not tempo_backup:
        print("Não foi possível obter o horário de backup ou o tempo de backup.")
        return

    tempo_backup_segundos = tempo_backup

    while True:
        if backup_hoje_realizado():

            with open("ultimo_backup.txt", 'r') as f:
                ultima_execucao = datetime.fromisoformat(f.read().strip())

            agora = datetime.now()
            proximo_horario = ultima_execucao + timedelta(seconds=tempo_backup_segundos)
            print(f"Backup já realizado no dia {ultima_execucao}. Aguardando próximo backup, {proximo_horario}")

            # Loop para exibir o tempo restante dinamicamente
            while True:
                diferenca = (proximo_horario - agora).total_seconds()

                dias = diferenca // 86400
                horas = (diferenca % 86400) // 3600
                minutos = (diferenca % 3600) // 60
                segundos = diferenca % 60
                print(
                    f"     Esperando {int(dias)} dias {int(horas):02}:{int(minutos):02}:{int(segundos):02} até o próximo backup...",
                    end="\r")

                if diferenca <= 0:
                    print("Chegou o horário do próximo backup. Reiniciando processo...")
                    break

                time.sleep(60)  # Atualiza a cada segundo

            continue

        agora = datetime.now().strftime("%H:%M:%S")
        print(f"Horário atual: {agora}")

        if agora == horario_agendado:
            print("Horário alcançado! Executando backups...")
            executar_backups()
            atualizar_data_ultimo_backup()
            time.sleep(30)
        elif agora > horario_agendado:
            print("O horário agendado passou. Executando os backups!")
            executar_backups()
            atualizar_data_ultimo_backup()
            time.sleep(30)
        else:
            print("Ainda não é o horário agendado. Aguardando...")
            atualizar_ultima_comunicacao()
            time.sleep(30)


# Função para iniciar o processo de backup
def processar_backups(request):
    # Rodar a função de backup em segundo plano usando threading
    threading.Thread(target=processar_backups_background, daemon=True).start()

    return HttpResponse("Backup em processamento. Verifique os logs para detalhes.")
