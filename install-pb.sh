#!/bin/bash
# Установщик KiriillBR Playerok Bot v2

GITHUB_REPO="silnikovkirill04-web/hehshe"
GITHUB_BRANCH="main"
GITHUB_FILE="jehsbhw.py"

RED='\033[1;91m'; CYAN='\033[1;96m'; GREEN='\033[1;92m'
YLW='\033[1;93m'; RESET='\033[0m'

clear
echo -e "${GREEN}==================================================="
echo -e "  KiriillBR Playerok Bot — установка"
echo -e "===================================================${RESET}"
echo -e "${CYAN}Источник: github.com/${GITHUB_REPO}${RESET}"
echo

# ── Имя пользователя ──
echo -ne "${CYAN}Имя Linux-пользователя [playerok]: ${RESET}"
read username
username=${username:-playerok}
[[ "$username" =~ ^[a-zA-Z][a-zA-Z0-9_-]+$ ]] || { echo -e "${RED}Ошибка в имени${RESET}"; exit 1; }

BOT_DIR="/home/$username/playerok-bot"
VENV_DIR="/home/$username/venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── [1/7] apt update ──
echo -e "\n${CYAN}[1/7] apt update${RESET}"
sudo apt update -y || exit 1

# ── [2/7] Системные пакеты ──
echo -e "${CYAN}[2/7] Системные пакеты${RESET}"
sudo apt install -y curl unzip git python3 python3-venv python3-pip \
    software-properties-common build-essential || exit 1

# ── [3/7] Python 3.11+ ──
echo -e "${CYAN}[3/7] Проверка Python 3.11+${RESET}"
SYSPY=""
for p in python3.11 python3.12 python3; do
    if command -v "$p" >/dev/null 2>&1; then
        v=$($p -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        mj=${v%.*}; mn=${v#*.}
        if [ "$mj" -ge 3 ] && [ "$mn" -ge 11 ]; then
            SYSPY="$p"; echo -e "  ${GREEN}✅ $p ($v)${RESET}"; break
        fi
    fi
done

if [ -z "$SYSPY" ]; then
    echo -e "  ${YLW}Python 3.11 нет — ставлю через deadsnakes${RESET}"
    sudo add-apt-repository -y ppa:deadsnakes/ppa || true
    sudo apt update -y
    if sudo apt install -y python3.11 python3.11-venv python3.11-dev; then
        SYSPY=python3.11
        echo -e "  ${GREEN}✅ Python 3.11 установлен${RESET}"
    else
        echo -e "${RED}❌ Не удалось поставить Python 3.11${RESET}"; exit 1
    fi
fi

# ── [4/7] Пользователь + venv ──
echo -e "${CYAN}[4/7] Пользователь $username + venv${RESET}"
id "$username" &>/dev/null || sudo useradd -m -s /bin/bash "$username" || exit 1

if [ ! -x "$PY" ]; then
    sudo -u "$username" "$SYSPY" -m venv "$VENV_DIR" || exit 1
fi
sudo -u "$username" "$PIP" install -q --upgrade pip setuptools wheel

# ── [5/7] Библиотеки (с проверкой) ──
echo -e "${CYAN}[5/7] Проверка и установка библиотек${RESET}"

check() { sudo -u "$username" "$PY" -c "$1" >/dev/null 2>&1; }

# pyTelegramBotAPI
if check "import telebot"; then
    echo -e "  ${GREEN}✅ pyTelegramBotAPI уже стоит${RESET}"
else
    echo -e "  ${YLW}→ ставлю pyTelegramBotAPI${RESET}"
    sudo -u "$username" "$PIP" install -q pyTelegramBotAPI || {
        echo -e "${RED}❌ Ошибка pyTelegramBotAPI${RESET}"; exit 1; }
    echo -e "  ${GREEN}✅ pyTelegramBotAPI установлен${RESET}"
fi

# curl-cffi==0.13.0 (строго — иначе playerokapi не работает)
CURVER=$(sudo -u "$username" "$PY" -c "import curl_cffi;print(curl_cffi.__version__)" 2>/dev/null)
if [ "$CURVER" = "0.13.0" ]; then
    echo -e "  ${GREEN}✅ curl-cffi 0.13.0 уже стоит${RESET}"
else
    echo -e "  ${YLW}→ ставлю curl-cffi 0.13.0 (было: ${CURVER:-нет})${RESET}"
    sudo -u "$username" "$PIP" install -q --force-reinstall "curl-cffi==0.13.0" || {
        echo -e "${RED}❌ Ошибка curl-cffi${RESET}"; exit 1; }
    echo -e "  ${GREEN}✅ curl-cffi 0.13.0 установлен${RESET}"
fi

# playerokapi (из GitHub, требует Python 3.11+)
if check "from playerokapi.account import Account"; then
    echo -e "  ${GREEN}✅ playerokapi уже стоит${RESET}"
else
    echo -e "  ${YLW}→ ставлю playerokapi из GitHub${RESET}"
    sudo -u "$username" "$PIP" install -q git+https://github.com/alleexxeeyy/PlayerokAPI.git || {
        echo -e "${RED}❌ Ошибка playerokapi${RESET}"; exit 1; }
    echo -e "  ${GREEN}✅ playerokapi установлен${RESET}"
fi

# ── [6/7] Код бота ──
echo -e "${CYAN}[6/7] Скачиваю код бота${RESET}"
sudo -u "$username" mkdir -p "$BOT_DIR" "$BOT_DIR/tmp"
URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${GITHUB_FILE}"
if ! sudo -u "$username" curl -fsSL "$URL" -o "$BOT_DIR/pb.py"; then
    echo -e "${RED}Не удалось скачать $URL${RESET}"; exit 1
fi
sudo chown -R "$username:$username" "$BOT_DIR"
echo -e "${GREEN}✅ Код: $BOT_DIR/pb.py${RESET}"

# Синтаксис
if sudo -u "$username" "$PY" -c "import ast; ast.parse(open('$BOT_DIR/pb.py').read())" 2>/dev/null; then
    echo -e "  ${GREEN}✅ синтаксис pb.py OK${RESET}"
else
    echo -e "${RED}❌ Синтаксис pb.py битый${RESET}"; exit 1
fi

# ── [7/7] Первый запуск + сервис ──
echo
echo -e "${GREEN}===================================================${RESET}"
echo -e "  Первый запуск — бот спросит:"
echo -e "  • ник бота (например sa)"
echo -e "  • токен Telegram"
echo -e "  • пароль админа"
echo -e "  • ID админа"
echo -e "  • прокси (Enter — пропустить)"
echo -e "  • GitHub (можно: ${GITHUB_REPO})"
echo -e "${GREEN}===================================================${RESET}"
echo -ne "${CYAN}Enter чтобы продолжить...${RESET}"
read

cd "$BOT_DIR"
sudo -u "$username" "$PY" "$BOT_DIR/pb.py"

# читаем instance из config.json
INSTANCE=$(sudo -u "$username" "$PY" -c "import json;print(json.load(open('$BOT_DIR/config.json')).get('instance',''))" 2>/dev/null)
if [ -z "$INSTANCE" ]; then
    echo -e "${RED}Не удалось прочитать instance из config.json${RESET}"; exit 1
fi
echo -e "${GREEN}✅ Инстанс: $INSTANCE${RESET}"

sudo mkdir -p "$BOT_DIR/$INSTANCE"
sudo chown -R "$username:$username" "$BOT_DIR/$INSTANCE"

echo -e "${CYAN}[7/7] Создаю сервис playerok-${INSTANCE}${RESET}"
sudo tee /etc/systemd/system/playerok-${INSTANCE}.service >/dev/null <<EOF
[Unit]
Description=Playerok Bot (${INSTANCE})
After=network.target

[Service]
Type=simple
User=$username
WorkingDirectory=$BOT_DIR
Environment=HOME=/home/$username
Environment=TMPDIR=$BOT_DIR/tmp
ExecStart=$PY $BOT_DIR/pb.py
Restart=always
RestartSec=10
StandardOutput=append:$BOT_DIR/${INSTANCE}/bot.log
StandardError=append:$BOT_DIR/${INSTANCE}/bot.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable playerok-${INSTANCE}
sudo systemctl restart playerok-${INSTANCE}

sleep 3
clear
echo -e "${GREEN}==================================================="
echo -e "  ✅ Готово! Инстанс: ${INSTANCE}"
echo -e "===================================================${RESET}"
echo
echo -e "📁 Папка:   ${CYAN}$BOT_DIR${RESET}"
echo -e "📁 Данные:  ${CYAN}$BOT_DIR/$INSTANCE${RESET}"
echo -e "🐍 Python:  ${CYAN}$PY${RESET}"
echo
echo -e "${GREEN}Управление:${RESET}"
echo -e "  sudo systemctl status playerok-${INSTANCE}"
echo -e "  sudo systemctl restart playerok-${INSTANCE}"
echo -e "  sudo systemctl stop playerok-${INSTANCE}"
echo -e "  sudo journalctl -u playerok-${INSTANCE} -f"
echo
echo -e "${GREEN}Логи:${RESET}"
echo -e "  tail -f $BOT_DIR/${INSTANCE}/bot.log"
echo
echo -e "${GREEN}Открой Telegram-бота и напиши /start${RESET}"
