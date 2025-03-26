api="XXXXXXXX"
secret="XXXXXXXXXXX"
bot_token="XXXXXXXXXXX"
chat_id="XXXXXXXXXXX"
# Bybit WebSocket URL
# Nếu chạy tài khoản thực thì bật dòng ở dưới, comment dòng thứ 2 lại
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/linear" 
# BYBIT_WS_URL = "wss://stream-testnet.bybit.com/v5/public/linear"

# Danh sách cặp giao dịch
SYMBOLS = ["ADAUSDT", "XRPUSDT", "DOGEUSDT"]

# Setting bot
TP_PERCENT = 0.005 #take profit theo % giá (0.5%)
PL_PERCENT = 0.02 # Đặt lệnh mỗi khi giá lên % (2%)