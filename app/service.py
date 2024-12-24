import os
import time
from datetime import datetime, timedelta
import requests
import environ
import json
from pathlib import Path

env = environ.Env()

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
    print(f"Salvar aqui: {pasta_equipamento}")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    caminho_arquivo = pasta_equipamento / f"{nome_equipamento}_{timestamp}.txt"

    try:
        # Se o conteúdo for uma string, salva diretamente
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            f.write(conteudo_backup)
        print(f"Backup salvo em: {caminho_arquivo}")
    except Exception as e:
        print(f"Erro ao salvar o backup no caminho {caminho_arquivo}: {e}")

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

    # Criando uma instância do cliente FTP
    ftp = FTP()

    # Conectando ao servidor FTP
    ftp = FTP(servidor_ftp)
    ftp.login(usuario_ftp, senha_ftp)

    # Verifica se o diretório existe e se não, cria o diretório
    try:
        ftp.mkd(pasta_destino)  # Cria o diretório de destino se não existir
    except:
        print(f"O diretório {pasta_destino} já existe no servidor FTP.")

    # Mudando para o diretório de destino
    ftp.cwd(pasta_destino)

    # Enviando o arquivo
    with open(caminho_arquivo, "rb") as f:
        ftp.storbinary(f"STOR {os.path.basename(caminho_arquivo)}", f)

    ftp.quit()
    print(f"Backup {caminho_arquivo} enviado via FTP para {pasta_destino}.")


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


def realizar_backup(equipamento):
    print(f"Iniciando backup para {equipamento['descricao']} ({equipamento['ip']})")

    comando_backup = equipamento['ScriptEquipment']['Script']
    protocolo = equipamento['access_type'].upper()

    try:
        # Acessa o equipamento e realiza o backup
        data = {
            "id": equipamento['id'],
            "ip": equipamento['ip'],
            "usuario": equipamento['usuarioacesso'],
            "senha": equipamento['senhaacesso'],
            "porta": equipamento['portaacesso'],
            "comando": comando_backup,
            "nome_equipamento": equipamento['descricao'],
            "protocolo": protocolo,
        }
        # Converte o dicionário em JSON
        json_data = json.dumps(data)
        print(json_data)

        # Realiza a chamada da API
        resposta = requests.post(f'{API_URL}/acessar_equipamento/', json=json_data, headers=HEADERS)

        # Verifique se a resposta da API foi bem-sucedida
        if resposta.status_code == 200:
            try:
                # Converte o texto da resposta para um dicionário
                conteudo_backup = json.loads(resposta.text)
                print(f"Conteúdo do backup: {conteudo_backup}")

                # Verifique se o conteúdo da resposta é um dicionário e contém a chave 'resultado'
                if isinstance(conteudo_backup, dict) and 'resultado' in conteudo_backup:
                    backup_data = conteudo_backup['resultado']
                    # Salva o backup localmente
                    caminho_arquivo = salvar_backup(equipamento['descricao'], backup_data)
                else:
                    print("A chave 'resultado' não foi encontrada na resposta ou o conteúdo não é um dicionário.")
                    # Se não houver a chave 'resultado', salvamos a resposta diretamente
                    caminho_arquivo = salvar_backup(equipamento['descricao'], conteudo_backup)

                # Envia o backup via FTP
                enviar_backup(equipamento['id'], caminho_arquivo, equipamento['descricao'])
            except Exception as e:
                print(f"Erro ao salvar ou enviar o backup: {e}")

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

        for equipamento in equipamentos:
            realizar_backup(equipamento)
    else:
        print(f"Erro ao buscar equipamentos: {response.status_code}")


# Obtém o horário agendado via API
def obter_horario_backup():
    url = f"{API_URL}/enterprises"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        empresas = response.json()
        if empresas and isinstance(empresas, list):
            horario_backup = empresas[0].get("horario_backup")
            print(f"Horário agendado para: {horario_backup}")
            return horario_backup
    print(f"Erro ao obter horário: {response.status_code}")
    return None


# Envia o backup via FTP
def enviar_backup(equipamento_id, caminho_arquivo, nome_equipamento):
    try:
        # Envia via FTP para o diretório correto
        enviar_arquivo_ftp(caminho_arquivo, nome_equipamento)

    except Exception as e:
        print(f"Erro no envio via FTP: {e}")


# Função principal para processar backups
def processar_backups(request):
    horario_agendado = obter_horario_backup()
    if not horario_agendado:
        print("Não foi possível obter o horário de backup.")
        return

    while True:
        # Verifica se o backup já foi realizado hoje
        if backup_hoje_realizado():
            print("Backup já realizado hoje. Aguardando próximo horário...")
            with open("ultimo_backup.txt", 'r') as f:
                ultima_execucao = datetime.fromisoformat(f.read().strip())

            agora = datetime.now()
            proximo_horario = ultima_execucao + timedelta(seconds=86400)  # Próximo horário após 24 horas

            # Calcula o tempo restante até o próximo horário
            diferenca = (proximo_horario - agora).total_seconds()
            if diferenca > 0:
                print(f"Esperando {diferenca // 3600} horas e {diferenca % 3600 // 60} minutos até o próximo backup...")
                time.sleep(diferenca)
            continue

        agora = datetime.now().strftime("%H:%M:%S")
        print(f"Horário atual: {agora}")

        if agora == horario_agendado:
            print("Horário alcançado! Executando backups...")
            executar_backups()
            atualizar_data_ultimo_backup()
            time.sleep(60)  # Evita execução duplicada
        elif agora > horario_agendado:
            print("O horário agendado passou. Executando os backups!")
            executar_backups()
            atualizar_data_ultimo_backup()
            time.sleep(60)
        else:
            print("Ainda não é o horário agendado. Aguardando...")
            time.sleep(30)

