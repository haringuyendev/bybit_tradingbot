import websockets
import json
from time import sleep
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from pybit.unified_trading import HTTP
import math

# Bybit API credentials
from bybit import api, secret, bot_token, chat_id, BYBIT_WS_URL, SYMBOLS, TP_PERCENT, PL_PERCENT

# Telegram Bot
bot = Bot(token=bot_token)

# Dictionary lưu trạng thái từng symbol
symbol_data = {
    symbol: {
        "buy_level": 0,
        "sell_level": 0,
        "buy_qty": 0,
        "sell_qty": 0,
        "count_buy":0,
        "count_sell":0,
        "PL_PERCENT_LV1":0.032,
        "NUM_POS_LV1": 5,
        "PL_PERCENT_LV2":0.016,
        "NUM_POS_LV2": 10,
        "PL_PERCENT_LV3":0.008,
        "NUM_POS_LV3": 20,
        "PL_PERCENT_LV4":0.004,
        "NUM_POS_LV4": 30,
    } for symbol in SYMBOLS
}
# Setting chạy testnet hay mainnet (Test net để test, mainnet để chạy tài khoản thực)
session = HTTP(
    # demo=True, # Nếu chạy tài khoản thực thì bỏ dòng này
    testnet=False, # Nếu chạy tài khoản thực chuyển sang False
    api_key=api,
    api_secret=secret,
)

# Hàm đặt lệnh 
async def place_order(symbol, side, quantity,pos_side):
    """Gửi lệnh mới trên Bybit"""
    try:
        response = session.place_order(
            category="linear",  # "spot" cho Spot Trading, "linear" cho Futures
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=quantity,
            timeInForce="PostOnly",
            positionIdx= 1 if pos_side=="Buy" else 2
        )
        if response["retCode"] == 0:
            print(f"✅  Đã đặt lệnh: {side}, {symbol}, {quantity}")
            await send_message_with_retry(f"✅  Đã đặt lệnh: {side}, {symbol}, {quantity}")
        else:
            print(f"❌ Lỗi đặt lệnh: {response}")
            await send_message_with_retry(f"❌ Lỗi đặt lệnh: {response}")
    except Exception as e:
        await send_message_with_retry(f"❌ Lỗi đặt lệnh: {e}")
        print(f"❌ Lỗi đặt lệnh: {e}")

async def send_message(message):
    """Gửi tin nhắn Telegram"""
    await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)

# Hàm gửi tin nhắn về telegram 
async def send_message_with_retry(message, retry_count=3, delay=1):
    """Gửi tin nhắn Telegram với retry"""
    for _ in range(retry_count):
        try:
            await send_message(message)
            break
        except Exception as e:
            print(f"Lỗi gửi tin nhắn: {e}")
            await asyncio.sleep(delay)

# Hàm lấy khối lượng nhỏ nhất của symbol
def get_min_notional(symbol):
    """Lấy giá trị minNotionalValue trên Bybit"""
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
        instruments = response.get("result", {}).get("list", [])

        for instrument in instruments:
            if instrument["symbol"] == symbol:
                print(instrument)
                return float(instrument["lotSizeFilter"]["minNotionalValue"])

        return 5.0  # Giá trị mặc định nếu không tìm thấy
    except Exception as e:
        print(f"❌ Lỗi lấy minNotionalValue: {e}")
        return 5.0
    
# Update giá take profit sau khi DCA 
async def update_take_profit(symbol, position_side):
    """Xóa TP cũ (nếu có) và đặt TP mới theo breakeven + 0.5% (Bybit API)"""
    try:
        # 1️⃣ Lấy thông tin vị thế mở
        positions = session.get_positions(category="linear", symbol=symbol)
        if not positions['result']['list']:
            return
        print(positions)
        position = next(
            (pos for pos in positions['result']['list'] if pos['side'] == position_side), None
        )
        if not position or float(position['size']) == 0:
            return
        
        breakeven_price = float(position['avgPrice'])

        # 2️⃣ Xác định giá TP
        if position_side == "Buy":
            tp_price = breakeven_price * (1 + TP_PERCENT)
        else:
            tp_price = breakeven_price * (1 - TP_PERCENT)

        # 3️⃣ Hủy lệnh TP cũ (nếu có)
        response=session.set_trading_stop(
            category="linear",
            symbol=symbol,
            takeProfit=tp_price,
            stopLoss=0,
            tpTriggerBy="MarkPrice",
            slTriggerB="IndexPrice",
            tpslMode="Full",
            positionIdx=1 if position_side=="Buy" else 2,
        )
        if response["retCode"] == 0:
            print(f"✅ Đã cập nhật TP: {symbol} {tp_price} {position_side}")
            await send_message_with_retry(f"✅ Đã cập nhật TP: {symbol} {tp_price} {position_side}")
        else:
            await send_message_with_retry(f"❌ Lỗi cập nhật TP: {response}")
            print(f"❌ Lỗi cập nhật TP: {response}")
       
        return response
    except Exception as e:
        await send_message_with_retry(f"❌ Lỗi cập nhật TP: {e}")
        print(f"❌ Lỗi cập nhật TP: {e}")

# Lấy khối lượng và giá khi khởi chạy bot 
async def get_position_qty(symbol):
    """Lấy số lượng vị thế (long, short) và giá vào lệnh trên Bybit"""
    try:
        response = session.get_positions(category="linear", symbol=symbol)
        positions = response.get("result", {}).get("list", [])

        buy_qty, sell_qty, entry_price_buy, entry_price_sell = 0, 0, 0, 0

        for pos in positions:
            if pos["symbol"] == symbol:
                position_amt = float(pos["size"])  # Kích thước vị thế
                entry_price = float(pos["avgPrice"])  # Giá vào lệnh trung bình
                position_side = pos["side"]  # LONG hoặc SHORT
                tp_price=pos["takeProfit"]
                if(tp_price==0 or tp_price==''):
                    await update_take_profit(symbol, position_side)

                print(position_side, position_amt, entry_price)

                if position_side == "Buy":
                    buy_qty = abs(position_amt)
                    entry_price_buy = entry_price
                elif position_side == "Sell":
                    sell_qty = abs(position_amt)
                    entry_price_sell = entry_price

        return buy_qty, sell_qty, entry_price_buy, entry_price_sell
    except Exception as e:
        await send_message_with_retry(f"❌ Lỗi lấy thông tin vị thế: {e}")
        print(f"❌ Lỗi lấy thông tin vị thế: {e}")
        return 0, 0, 0, 0

# Func quản lý orders 
async def manage_orders(symbol, price):
    """Quản lý lệnh mua/bán dựa trên giá"""
    data = symbol_data[symbol]
    buy_qty, sell_qty, entry_price_buy, entry_price_sell = await get_position_qty(symbol)
    
    if buy_qty == 0:
        data["buy_level"] = 0
        data["count_buy"]=0
    elif buy_qty>0 and data["buy_level"]==0:
        data["buy_level"] = entry_price_buy
        data["buy_qty"] = buy_qty

    if sell_qty == 0:
        data["sell_level"] = 0
        data["count_sell"]=0
    elif sell_qty>0 and data["sell_level"]==0:
        data["sell_level"] = entry_price_sell
        data["sell_qty"] = sell_qty

    if data["buy_level"] == 0:
        data["buy_level"] = price
        min_qty = (get_min_notional(symbol) + 1) / price
        data["buy_qty"] = math.ceil(min_qty) # Sửa số lượng theo cần thiết
        data["count_buy"]+=1
        await place_order(symbol, "Buy", data["buy_qty"],"Buy")
        await update_take_profit(symbol, "Buy")
    else:
        tp_price_down = data["buy_level"] * (1 - PL_PERCENT)
        if(data["count_buy"]<=data["NUM_POS_LV1"]):
            tp_price_down = data["buy_level"] * (1 - data["PL_PERCENT_LV1"])
        elif(data["count_buy"]>data["NUM_POS_LV1"] and data["count_buy"]<=data["NUM_POS_LV2"]):
            tp_price_down = data["buy_level"] * (1 - data["PL_PERCENT_LV2"])
        elif(data["count_buy"]>data["NUM_POS_LV2"] and data["count_buy"]<=data["NUM_POS_LV3"]):
            tp_price_down = data["buy_level"] * (1 - data["PL_PERCENT_LV3"])
        elif(data["count_buy"]>data["NUM_POS_LV3"] and data["count_buy"]<=data["NUM_POS_LV4"]):
            tp_price_down = data["buy_level"] * (1 - data["PL_PERCENT_LV4"])
        else:
            tp_price_down = data["buy_level"] * (1 - data["PL_PERCENT_LV4"])
        if price <= tp_price_down:
            data["buy_level"] = price
            min_qty = (get_min_notional(symbol) + 1) / price
            data["buy_qty"] += math.ceil(min_qty)
            data["count_buy"]+=1
            await place_order(symbol, "Buy", data["buy_qty"], "Buy")
            await update_take_profit(symbol, "Buy")

    if data["sell_level"] == 0:
        data["sell_level"] = price
        min_qty = (get_min_notional(symbol) + 1) / price
        data["sell_qty"] = math.ceil(min_qty)
        data["count_sell"]+=1
        await place_order(symbol, "Sell", data["sell_qty"], "Sell")
        await update_take_profit(symbol, "Sell")
    else:
        tp_price_up = data["sell_level"] * (1 + PL_PERCENT)
        if(data["count_sell"]<=data["NUM_POS_LV1"]):
            tp_price_up = data["sell_level"] * (1 + data["PL_PERCENT_LV1"])
        elif(data["count_sell"]>data["NUM_POS_LV1"] and data["count_sell"]<=data["NUM_POS_LV2"]):
            tp_price_up = data["sell_level"] * (1 + data["PL_PERCENT_LV2"])
        elif(data["count_sell"]>data["NUM_POS_LV2"] and data["count_sell"]<=data["NUM_POS_LV3"]):
            tp_price_up = data["sell_level"] * (1 + data["PL_PERCENT_LV3"])
        elif(data["count_sell"]>data["NUM_POS_LV3"] and data["count_sell"]<=data["NUM_POS_LV4"]):
            tp_price_up = data["sell_level"] * (1 + data["PL_PERCENT_LV4"])
        else:
            tp_price_up = data["sell_level"] * (1 + data["PL_PERCENT_LV4"])
        if price >= tp_price_up:
            data["sell_level"] = price
            min_qty = (get_min_notional(symbol) + 1) / price
            data["sell_qty"] += math.ceil(min_qty)
            data["count_sell"]+=1
            await place_order(symbol, "Sell", data["sell_qty"], "Sell")
            await update_take_profit(symbol, "Sell")

    print("Buy Level: ",data["buy_level"], "Buy Qty: ",data["buy_qty"], "Sell Level: ",data["sell_level"], "Sell Qty: ",data["sell_qty"])

async def bybit_ws(symbol):
    """Lắng nghe WebSocket cho từng cặp tiền & tự động reconnect"""
    while True:
        try:
            async with websockets.connect(BYBIT_WS_URL, ping_interval=10, ping_timeout=5) as websocket:
                print(f"✅ WebSocket kết nối thành công: {symbol}")

                subscribe_message = {
                    "op": "subscribe",
                    "args": [f"tickers.{symbol}"]
                }
                await websocket.send(json.dumps(subscribe_message))

                while True:
                    try:
                        response = await websocket.recv()
                        data = json.loads(response)

                        if "topic" in data and "tickers" in data["topic"]:
                            symbol = data["topic"].split(".")[1]
                            if "data" in data and "ask1Price" in data["data"]:
                                price = float(data["data"]["ask1Price"])
                                print(f"{symbol} giá hiện tại: {price}")
                                await manage_orders(symbol, price)

                    except websockets.exceptions.ConnectionClosed as e:
                        print(f"🔴 Mất kết nối WebSocket {symbol}: {e}")
                        break  # Thoát khỏi vòng lặp để reconnect

                    except Exception as e:
                        print(f"⚠️ Lỗi WebSocket {symbol}: {e}")

        except Exception as e:
            print(f"🔄 Đang thử reconnect WebSocket {symbol} sau 5 giây... {e}")
            await asyncio.sleep(5)  # Đợi 5 giây rồi thử kết nối lại

async def main():
    """Tạo task riêng biệt cho từng cặp tiền"""
    tasks = [asyncio.create_task(bybit_ws(symbol)) for symbol in SYMBOLS]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
