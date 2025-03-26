Bybit Trading Bot

Giới thiệu

Đây là bot giao dịch tự động sử dụng WebSocket để lấy giá real-time từ Bybit Bot có khả năng tự động reconnect khi mất kết nối và quản lý các lệnh giao dịch dựa trên giá thị trường.

Tính năng

✅ Lắng nghe giá real-time từ Bybit
✅ Tự động reconnect khi mất kết nối WebSocket
✅ Xử lý lệnh dựa trên giá nhận được
✅ Hỗ trợ nhiều cặp tiền cùng lúc
✅ Chạy bất đồng bộ (async) để tối ưu hiệu suất

Cài đặt

1. Yêu cầu

Python 3.12+

Thư viện cần thiết:

pip install -r requirements.txt

2. Cấu trúc dự án

my-bot/
├── bybit_tradingbot.py   # Bot Bybit
├── bybit.py             # Cấu hình config
├── requirements.txt      # Danh sách thư viện
└── README.md             # Tài liệu hướng dẫn

3. Chạy bot

Chạy bot Bybit:

python3 bybit_tradingbot.py


Xử lý lỗi & Reconnect

Nếu kết nối WebSocket bị mất, bot sẽ tự động reconnect sau 5 giây.

Nếu có lỗi, bot sẽ tiếp tục chạy thay vì bị dừng.
