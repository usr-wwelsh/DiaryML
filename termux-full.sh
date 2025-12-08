#!/data/data/com.termux/files/usr/bin/bash
# DiaryML Termux Client - Chat with your AI diary from Android
# Dependencies: curl, jq (install with: pkg install curl jq)
# Usage: bash termux-full.sh

CONFIG_DIR="$HOME/.diaryml"
TOKEN_FILE="$CONFIG_DIR/token"
SESSION_FILE="$CONFIG_DIR/session"
API_FILE="$CONFIG_DIR/api_url"
API=""
TOKEN=""
SESSION_ID=""

mkdir -p "$CONFIG_DIR"
[ -f "$TOKEN_FILE" ] && TOKEN=$(cat "$TOKEN_FILE")
[ -f "$SESSION_FILE" ] && SESSION_ID=$(cat "$SESSION_FILE")
[ -f "$API_FILE" ] && API=$(cat "$API_FILE")

if [ -z "$API" ]; then
echo "First time setup!"
echo "Enter your DiaryML server URL"
echo "Example: http://192.168.1.100:8000"
read -p "URL: " API
echo "$API" > "$API_FILE"
fi

login() {
echo "Enter DiaryML password:"
read -s PASS
echo ""
RESP=$(curl -s "$API/api/mobile/login" -H "Content-Type: application/json" -d "{\"password\":\"$PASS\"}")
TOKEN=$(echo "$RESP" | jq -r '.access_token')
if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
echo "Login failed!"
exit 1
fi
echo "$TOKEN" > "$TOKEN_FILE"
echo "Login successful!"
}

main_menu() {
clear
echo "================================"
echo "   DiaryML Termux Chat"
echo "================================"
echo ""
echo "1) Chat"
echo "2) Switch Model"
echo "3) Manage Sessions"
echo "4) Settings"
echo "5) Exit"
echo ""
read -p "Select: " choice
case "$choice" in
1) chat_interface ;;
2) switch_model ;;
3) manage_sessions ;;
4) settings_menu ;;
5) exit 0 ;;
*) main_menu ;;
esac
}

settings_menu() {
clear
echo "================================"
echo "   Settings"
echo "================================"
echo ""
echo "Current server: $API"
echo ""
echo "1) Change server URL"
echo "2) Re-login"
echo "3) Clear all data"
echo "4) Back"
echo ""
read -p "Select: " choice
case "$choice" in
1)
echo ""
read -p "New server URL: " NEW_API
echo "$NEW_API" > "$API_FILE"
API="$NEW_API"
echo "Updated!"
sleep 1
settings_menu
;;
2)
rm -f "$TOKEN_FILE"
TOKEN=""
login
settings_menu
;;
3)
read -p "Delete all local data? (yes/no): " confirm
if [ "$confirm" = "yes" ]; then
rm -rf "$CONFIG_DIR"
echo "Cleared! Restart the script."
exit 0
fi
settings_menu
;;
4) main_menu ;;
*) settings_menu ;;
esac
}

chat_interface() {
clear
echo "================================"
echo "   Chat (type 'back' to exit)"
echo "================================"
echo ""
if [ -n "$SESSION_ID" ]; then
echo "Session: #$SESSION_ID"
echo ""
echo "Recent messages:"
MSGS=$(curl -s "$API/api/mobile/chat/sessions/$SESSION_ID/messages" -H "Authorization: Bearer $TOKEN")
echo "$MSGS" | jq -r '.messages[-3:][]? | if .role == "user" then "You: \(.content)" else "AI: \(.content)" end' 2>/dev/null | head -10
echo ""
fi
echo "Type 'back' (menu) | 'new' (new chat)"
echo ""
while true; do
read -p "You: " MSG
case "$MSG" in
back) main_menu; return ;;
new)
SESSION_ID=""
echo "" > "$SESSION_FILE"
echo "New chat started!"
;;
"") continue ;;
*)
FORM_DATA="-F \"message=$MSG\""
[ -n "$SESSION_ID" ] && FORM_DATA="$FORM_DATA -F \"session_id=$SESSION_ID\""
RESP=$(curl -s "$API/api/mobile/chat" -H "Authorization: Bearer $TOKEN" -F "message=$MSG" $([ -n "$SESSION_ID" ] && echo "-F session_id=$SESSION_ID"))
AI_RESP=$(echo "$RESP" | jq -r '.response')
SESSION_ID=$(echo "$RESP" | jq -r '.session_id')
echo "$SESSION_ID" > "$SESSION_FILE"
echo ""
echo "AI: $AI_RESP"
echo ""
;;
esac
done
}

switch_model() {
clear
echo "================================"
echo "   Switch AI Model"
echo "================================"
echo ""
MODELS=$(curl -s "$API/api/mobile/models/list" -H "Authorization: Bearer $TOKEN")
CURRENT=$(echo "$MODELS" | jq -r '.current_model.filename // "None"')
echo "Current: $CURRENT"
echo ""
echo "Available models:"
echo "$MODELS" | jq -r '.models[] | "\(.name) - \(.size)"'
echo ""
read -p "Enter model filename (or Enter to cancel): " MODEL
if [ -n "$MODEL" ]; then
echo "Switching model..."
SWITCH_RESP=$(curl -s "$API/api/mobile/models/switch" -H "Authorization: Bearer $TOKEN" -F "model_filename=$MODEL")
SUCCESS=$(echo "$SWITCH_RESP" | jq -r '.success')
if [ "$SUCCESS" = "true" ]; then
echo "Model switched successfully!"
else
echo "Failed to switch model"
fi
sleep 2
fi
main_menu
}

manage_sessions() {
clear
echo "================================"
echo "   Chat Sessions"
echo "================================"
echo ""
SESSIONS=$(curl -s "$API/api/mobile/chat/sessions" -H "Authorization: Bearer $TOKEN")
COUNT=$(echo "$SESSIONS" | jq '.sessions | length')
if [ "$COUNT" -eq 0 ]; then
echo "No sessions found"
read -p "Press Enter..."
main_menu
return
fi
echo "$SESSIONS" | jq -r '.sessions[] | "#\(.id) - \(.created_at)"'
echo ""
echo "1) Load session"
echo "2) View history"
echo "3) Delete session"
echo "4) Back"
echo ""
read -p "Select: " choice
case "$choice" in
1)
read -p "Session ID: " SID
SESSION_ID="$SID"
echo "$SESSION_ID" > "$SESSION_FILE"
echo "Loaded session #$SID"
sleep 1
chat_interface
;;
2)
read -p "Session ID: " SID
clear
echo "Session #$SID History:"
echo "================================"
HIST=$(curl -s "$API/api/mobile/chat/sessions/$SID/messages" -H "Authorization: Bearer $TOKEN")
echo "$HIST" | jq -r '.messages[] | if .role == "user" then "\nYou: \(.content)" else "AI: \(.content)" end'
echo ""
read -p "Press Enter..."
manage_sessions
;;
3)
read -p "Delete session ID: " SID
curl -s -X DELETE "$API/api/mobile/chat/sessions/$SID" -H "Authorization: Bearer $TOKEN" > /dev/null
echo "Deleted"
sleep 1
manage_sessions
;;
4) main_menu ;;
*) manage_sessions ;;
esac
}

[ -z "$TOKEN" ] && login
main_menu
