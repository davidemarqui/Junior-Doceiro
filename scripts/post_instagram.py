import os
import json
import time
import requests
import subprocess

IG_USER_ID = os.getenv("IG_USER_ID")
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
IMAGE_URL = os.getenv("IMAGE_URL")
TARGET_PROFILE_ID = os.getenv("TARGET_PROFILE_ID")

GRAPH_API_BASE = "https://graph.facebook.com/v24.0"
COUNTER_FILE = "post_counter.json"

required_env = {
    "IG_USER_ID": IG_USER_ID,
    "IG_ACCESS_TOKEN": ACCESS_TOKEN,
    "IMAGE_URL": IMAGE_URL,
    "TARGET_PROFILE_ID": TARGET_PROFILE_ID,
}

missing_env = [key for key, value in required_env.items() if not value]
if missing_env:
    raise EnvironmentError(f"Variáveis de ambiente ausentes: {', '.join(missing_env)}")


def api_get(path: str, params: dict | None = None) -> dict:
    response = requests.get(
        f"{GRAPH_API_BASE}/{path}",
        params={**(params or {}), "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    if response.status_code != 200:
        print("Erro na chamada GET:")
        print(response.text)
        response.raise_for_status()
    return response.json()


def api_post(path: str, data: dict | None = None) -> dict:
    response = requests.post(
        f"{GRAPH_API_BASE}/{path}",
        data={**(data or {}), "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    if response.status_code != 200:
        print("Erro na chamada POST:")
        print(response.text)
        response.raise_for_status()
    return response.json()


# 1. Ler contador
with open(COUNTER_FILE, "r") as f:
    data = json.load(f)

current_count = data.get("count", 0) + 1

caption = f"""Dia {current_count}

Guh Guh Dah Dah Comendo um docinho 🍬
"""


# 2. Criar container de mídia
media_response = api_post(
    f"{IG_USER_ID}/media",
    {
        "image_url": IMAGE_URL,
        "caption": caption,
    },
)

creation_id = media_response["id"]
print("Container criado:", creation_id)


# 3. Aguardar processamento
for attempt in range(1, 11):
    status_response = api_get(creation_id, {"fields": "status_code"})
    status = status_response.get("status_code")

    print(f"Tentativa {attempt} - status da mídia: {status}")

    if status == "FINISHED":
        break
    if status == "ERROR":
        raise RuntimeError("Erro no processamento da mídia")

    time.sleep(3)
else:
    raise TimeoutError("Timeout aguardando a mídia ficar pronta")


# 4. Publicar no seu perfil
api_post(
    f"{IG_USER_ID}/media_publish",
    {"creation_id": creation_id},
)
print(f"Post do Dia {current_count} publicado com sucesso.")


# 5. Atualizar contador
data["count"] = current_count
with open(COUNTER_FILE, "w") as f:
    json.dump(data, f, indent=2)


# 6. Commit automático do contador
subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
subprocess.run(["git", "add", COUNTER_FILE], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", f"chore: contador Instagram dia {current_count}"],
    capture_output=True,
    text=True,
)

if commit.returncode == 0:
    subprocess.run(["git", "push"], check=True)
else:
    print("Nada para commitar")


# 7. Descobrir username da conta autenticada
me = api_get(IG_USER_ID, {"fields": "username"})
my_username = me.get("username")

if not my_username:
    raise RuntimeError("Não foi possível obter o username da conta autenticada")


# 8. Buscar o post mais recente do perfil alvo
latest_media_response = api_get(
    f"{TARGET_PROFILE_ID}/media",
    {"fields": "id,caption,timestamp,permalink", "limit": 1},
)

latest_media_list = latest_media_response.get("data", [])
if not latest_media_list:
    raise RuntimeError("O perfil alvo não possui posts disponíveis")

latest_media = latest_media_list[0]
latest_media_id = latest_media["id"]

print("Post mais recente do perfil alvo:", latest_media_id)
if latest_media.get("permalink"):
    print("Link:", latest_media["permalink"])


# 9. Verificar se já existe comentário da sua conta nesse post
already_commented = False
comments_response = api_get(
    f"{latest_media_id}/comments",
    {"fields": "id,text,username", "limit": 50},
)

while True:
    for comment in comments_response.get("data", []):
        if comment.get("username") == my_username:
            already_commented = True
            break

    if already_commented:
        break

    next_page = comments_response.get("paging", {}).get("next")
    if not next_page:
        break

    next_response = requests.get(next_page, timeout=30)
    if next_response.status_code != 200:
        print("Erro ao paginar comentários:")
        print(next_response.text)
        next_response.raise_for_status()

    comments_response = next_response.json()


# 10. Comentar apenas se ainda não comentou
if already_commented:
    print("Comentário já existe no último post do perfil alvo. Nada a fazer.")
else:
    comment_result = api_post(
        f"{latest_media_id}/comments",
        {"message": "Bença Pai"},
    )
    print("Comentário publicado com sucesso:", comment_result.get("id"))

print("Processo concluído.")
