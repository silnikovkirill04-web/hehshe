#!/bin/bash
# Установщик KiriillBR Playerok Bot

GITHUB_REPO="silnikovkirill04-web/hehshe"
GITHUB_BRANCH="main"
GITHUB_FILE="jehsbhw.py"

RED='\033[1;91m'; CYAN='\033[1;96m'; GREEN='\033[1;92m'; RESET='\033[0m'

clear
echo -e "${GREEN}==================================================="
echo -e "  KiriillBR Playerok Bot — установка"
echo -e "===================================================${RESET}"
echo -e "${CYAN}Источник: github.com/${GITHUB_REPO}${RESET}"
echo

echo -ne "${CYAN}Имя Linux-пользователя [playerok]: ${RESET}"
read username
username=${username:-playerok}

[[ "$username" =~ ^[a-zA-Z][a-zA-Z0-9_-]+$ ]] || { echo -e "${RED}Ошибка${RESET}"; exit 1; }

echo -e "${CYAN}[1/6] apt update${RESET}"
sudo apt update -y || exit 1

echo -e "${CYAN}[2/6] Пакеты${RESET}"
sudo apt install -y curl unzip python3 python3-venv python3-pip git || exit 1

echo -e "${CYAN}[3/6] Пользователь${RESET}"
id "$username" &>/dev/null || sudo useradd -m -s /bin/bash "$username" || exit 1

echo -e "${CYAN}[4/6] venv + зависимости${RESET}"
sudo -u "$username" python3 -m venv "/home/$username/venv" || exit 1
sudo -u "$username" "/home/$username/venv/bin/pip" install -q --upgrade pip
sudo -u "$username" "/home/$username/venv/bin/pip" install -q pyTelegramBotAPI curl_cffi requests
sudo -u "$username" "/home/$username/venv/bin/pip" install -q git+https://github.com/alleexxeeyy/PlayerokAPI.git || true

echo -e "${CYAN}[5/6] Скачиваю код бота${RESET}"
BOT_DIR="/home/$username/playerok-bot"
sudo -u "$username" mkdir -p "$BOT_DIR"
URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/${GITHUB_FILE}"
if ! sudo -u "$username" curl -fsSL "$URL" -o "$BOT_DIR/pb.py"; then
    echo -e "${RED}Не удалось скачать $URL${RESET}"
    exit 1
fi
echo -e "${GREEN}✅ Код скачан: $BOT_DIR/pb.py${RESET}"

echo
echo -e "${GREEN}==================================================="
echo -e "  Первый запуск — бот спросит:"
echo -e "  • ник бота (например snahbshs)"
echo -e "  • токен"
echo -e "  • пароль админа"
echo -e "  • ID админа"
echo -e "  • прокси (можно пропустить)"
echo -e "  • GitHub (можешь ввести: ${GITHUB_REPO})"
echo -e "===================================================${RESET}"
echo -ne "${CYAN}Enter чтобы продолжить...${RESET}"
read

sudo -u "$username" "/home/$username/venv/bin/python" "$BOT_DIR/pb.py" <&1

INSTANCE=$(sudo -u "$username" cat "$BOT_DIR/.instance" 2>/dev/null | tr -d '\n')
if [ -z "$INSTANCE" ]; then
    echo -e "${RED}Ник не сохранён — что-то пошло не так${RESET}"
    exit 1
fi

echo -e "${CYAN}[6/6] Создаю сервис playerok-${INSTANCE}${RESET}"
sudo tee /etc/systemd/system/playerok-${INSTANCE}.service >/dev/null <<EOF
[Unit]
Description=Playerok Bot (${INSTANCE})
After=network.target

[Service]
Type=simple
User=$username
WorkingDirectory=$BOT_DIR
Environment=INSTANCE=${INSTANCE}
ExecStart=/home/$username/venv/bin/python $BOT_DIR/pb.py
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

sleep 2
clear
echo -e "${GREEN}==================================================="
echo -e "  ✅ Готово! Ник: ${INSTANCE}"
echo -e "===================================================${RESET}"
echo
echo -e "📁 Папка:  ${CYAN}$BOT_DIR/$INSTANCE${RESET}"
echo
echo -e "${GREEN}Управление:${RESET}"
echo -e "  sudo systemctl status playerok-${INSTANCE}"
echo -e "  sudo systemctl restart playerok-${INSTANCE}"
echo -e "  sudo journalctl -u playerok-${INSTANCE} -f"
echo
echo -e "${GREEN}Открой Telegram-бота и напиши /start${RESET}"
