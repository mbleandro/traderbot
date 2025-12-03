import asyncio
import os

import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
CHAT_ID = os.getenv("CHAT_ID")
WALLET_KEY = os.getenv("WALLET_KEY")

# Dicionário com processos ativos
PROCESSES = {}

# Mensagens já processadas
processed_messages = set()


def load_processed_messages():
    try:
        with open("processed_messages.txt") as f:
            for line in f:
                processed_messages.add(int(line.strip()))
    except FileNotFoundError:
        pass


def save_processed_messages():
    with open("processed_messages.txt", "w") as f:
        for msg_id in processed_messages:
            f.write(f"{msg_id}\n")


async def get_updates(session, offset=None):
    url = f"{BASE_URL}/getUpdates"

    params = {
        "timeout": 60  # long polling (melhor que ficar fazendo várias requisições)
    }

    if offset is not None:
        params["offset"] = offset

    async with session.get(url, params=params) as resp:
        data = await resp.json()
        print(resp.status)
        print(data)
        return data


async def send_message(session, chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    async with session.post(url, data={"chat_id": chat_id, "text": text}) as _:
        pass


async def start_process(name, coin, target, profit):
    if name in PROCESSES and PROCESSES[name].returncode is None:
        return f"❌ Já existe um processo ativo com esse nome: {name}"

    logfile = open(f"{name}.log", "a")
    # Executa processo async
    proc = await asyncio.create_subprocess_exec(
        "python3",
        "main.py",
        "run",
        coin,
        "target_value",
        "60",
        f"--wallet-key={WALLET_KEY}",
        "--api=jupiter",
        "--notification-service=telegram",
        f"--notification-args=chat_id={CHAT_ID} token={BOT_TOKEN}",
        "--websocket",
        f"target_buy_price={target} target_profit_percent={profit}",
        stdout=logfile,
        stderr=logfile,
    )

    PROCESSES[name] = proc
    return f"🚀 Processo '{name}' iniciado. PID = {proc.pid}"


async def stop_process(name):
    if name not in PROCESSES:
        return f"⚠️ Nenhum processo chamado '{name}'."

    proc = PROCESSES[name]

    if proc.returncode is not None:
        return f"ℹ️ Processo '{name}' já havia terminado."

    proc.terminate()
    return f"🛑 Processo '{name}' finalizado."


def list_PROCESSES():
    if not PROCESSES:
        return "Nenhum processo registrado."

    msg = "📌 Processos:\n"
    for name, proc in PROCESSES.items():
        status = "🟢 rodando" if proc.returncode is None else "🔴 finalizado"
        msg += f"- {name}: PID {proc.pid} — {status}\n"

    return msg


async def main_loop():
    offset = None
    load_processed_messages()

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                updates = await get_updates(session, offset)

                if "result" not in updates:
                    await asyncio.sleep(1)
                    continue

                for update in updates["result"]:
                    offset = update["update_id"] + 1

                    if "message" not in update or "text" not in update["message"]:
                        continue

                    message = update["message"]["text"]
                    message_id = update["message"]["message_id"]
                    chat_id = str(update["message"]["chat"]["id"])

                    if chat_id != CHAT_ID:
                        continue

                    if message_id in processed_messages:
                        continue

                    processed_messages.add(message_id)
                    save_processed_messages()

                    parts = message.split()
                    cmd = parts[0]

                    # ------------------------------------ COMANDOS
                    if cmd == "/start":
                        if len(parts) < 4:
                            await send_message(
                                session, chat_id, "⚠️ Use: /start coin target profit"
                            )
                            continue
                        name = parts[1] + "_" + parts[2] + "_" + parts[3]
                        msg = await start_process(name, parts[1], parts[2], parts[3])
                        await send_message(session, chat_id, msg)

                    elif cmd == "/stop":
                        if len(parts) < 2:
                            await send_message(
                                session, chat_id, "⚠️ Use: /stopproc nome"
                            )
                            continue
                        name = parts[1]
                        msg = await stop_process(name)
                        await send_message(session, chat_id, msg)

                    elif cmd == "/list":
                        await send_message(session, chat_id, list_PROCESSES())

                    elif cmd == "/help":
                        await send_message(
                            session,
                            chat_id,
                            "/start coin target profit\n"
                            "/stop nome\n"
                            "/list\n"
                            "/help\n"
                            "/ping\n"
                            "/log nome\n"
                            "/clear",
                        )

                    elif cmd == "/ping":
                        await send_message(session, chat_id, "Pong!")

                    elif cmd == "/log":
                        if len(parts) < 2:
                            await send_message(session, chat_id, "⚠️ Use: /log nome")
                            continue
                        name = parts[1]
                        with open(f"{name}.log") as f:
                            lines = f.readlines()[-6:]  # pega as últimas 6 linhas
                            await send_message(session, chat_id, "".join(lines))

                    elif cmd == "/clear":
                        running = {
                            name: proc
                            for name, proc in PROCESSES.items()
                            if proc.returncode is None
                        }
                        PROCESSES.clear()
                        PROCESSES.update(running)
                        await send_message(session, chat_id, "✅ Processos finalizados")
            except Exception as ex:
                print(f"Erro no loop principal: {str(ex)}")

            await asyncio.sleep(0.3)


if __name__ == "__main__":
    print("Bot rodando (async)...")
    asyncio.run(main_loop())
